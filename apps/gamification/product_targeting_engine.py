"""
AI Priority Engine untuk mission generation (Random Forest + TOPSIS).

Modul ini framework-agnostic (tidak menyentuh ORM/Django) supaya gampang
diuji standalone — jalankan `python product_targeting_engine.py` untuk demo.
Integrasi ke Django ada di services.py: data produk & transaksi di-feed
sebagai list of dict, hasilnya dipakai untuk memilih produk mission.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Mapping, Optional, Sequence, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

DictLike = Mapping[str, object]

# XP Reward = 20 + ((Current Level - 1) x 5)
BASE_XP = 20
XP_STEP_PER_LEVEL = 5

# GMV Target = Rp100,000 + ((Current Level - 1) x Rp50,000)
BASE_GMV_TARGET = 100_000
GMV_STEP_PER_LEVEL = 50_000

# Deadline (Days) = max(21 - (floor((Current Level - 1) / 5) x 3), 9)
BASE_DEADLINE_DAYS = 21
DEADLINE_STEP_DAYS = 3
DEADLINE_STEP_EVERY_LEVELS = 5
MIN_DEADLINE_DAYS = 9


def xp_reward_for_level(level: int) -> int:
    """XP Reward = 20 + ((Current Level - 1) x 5)"""
    level = max(int(level), 1)
    return BASE_XP + (level - 1) * XP_STEP_PER_LEVEL


def gmv_target_for_level(level: int) -> int:
    """GMV Target = Rp100,000 + ((Current Level - 1) x Rp50,000)"""
    level = max(int(level), 1)
    return BASE_GMV_TARGET + (level - 1) * GMV_STEP_PER_LEVEL


def deadline_days_for_level(level: int) -> int:
    """Deadline (Days) = max(21 - (floor((Current Level - 1) / 5) x 3), 9)"""
    level = max(int(level), 1)
    reduction = ((level - 1) // DEADLINE_STEP_EVERY_LEVELS) * DEADLINE_STEP_DAYS
    return max(BASE_DEADLINE_DAYS - reduction, MIN_DEADLINE_DAYS)


def target_quantity_for_gmv(gmv_target: float, product_price: float) -> int:
    """Target Quantity = Floor(GMV Target / Product Price), minimum 1 unit."""
    price = float(product_price or 0)
    if price <= 0:
        return 0
    qty = math.floor(gmv_target / price)
    return max(qty, 1)


FEATURE_COLS = [
    'price', 'current_stock', 'days_until_expired',
    'monthly_transaction_count', 'hist_avg_qty', 'stock_to_sales_ratio',
]


def _to_date(value) -> Optional[date]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def _build_features(
    products: Sequence[DictLike],
    transactions: Sequence[DictLike],
    today: date,
) -> pd.DataFrame:
    prod_df = pd.DataFrame(list(products))
    if prod_df.empty:
        return prod_df

    prod_df['price'] = prod_df['price'].astype(float)
    prod_df['current_stock'] = prod_df['current_stock'].astype(float)
    prod_df['expired_date'] = prod_df['expired_date'].apply(_to_date)

    tx_df = pd.DataFrame(list(transactions))
    if tx_df.empty:
        tx_df = pd.DataFrame(columns=['product_id', 'quantity', 'transaction_date'])
    else:
        tx_df['transaction_date'] = tx_df['transaction_date'].apply(_to_date)
        tx_df['quantity'] = tx_df['quantity'].astype(float)

    # Histori transaksi 60 hari terakhir dipakai sebagai basis fitur.
    cutoff_60 = today - timedelta(days=60)
    tx_60 = tx_df[tx_df['transaction_date'] >= cutoff_60] if not tx_df.empty else tx_df
    tx_stats = (
        tx_60.groupby('product_id')['quantity']
        .agg(tx_count='count', avg_qty='mean')
        .reset_index()
        if not tx_60.empty else pd.DataFrame(columns=['product_id', 'tx_count', 'avg_qty'])
    )

    feat = prod_df.merge(tx_stats, on='product_id', how='left')
    feat[['tx_count', 'avg_qty']] = feat[['tx_count', 'avg_qty']].fillna(0)

    feat['days_until_expired'] = feat['expired_date'].apply(
        lambda d: (d - today).days if d is not None else 90
    )
    feat['monthly_transaction_count'] = feat['tx_count'] * (30 / 60)
    feat['hist_avg_qty'] = feat['avg_qty']
    feat['stock_to_sales_ratio'] = feat['current_stock'] / feat['hist_avg_qty'].replace(0, 0.5)

    # Label training: total quantity terjual 30 hari terakhir per produk.
    cutoff_30 = today - timedelta(days=30)
    tx_30 = tx_df[tx_df['transaction_date'] >= cutoff_30] if not tx_df.empty else tx_df
    label_stats = (
        tx_30.groupby('product_id')['quantity'].sum().reset_index(name='qty_30d')
        if not tx_30.empty else pd.DataFrame(columns=['product_id', 'qty_30d'])
    )
    feat = feat.merge(label_stats, on='product_id', how='left')
    feat['qty_30d'] = feat['qty_30d'].fillna(0)

    return feat


def _train_model(feat: pd.DataFrame) -> RandomForestRegressor:
    X = feat[FEATURE_COLS]
    y = feat['qty_30d']

    model = RandomForestRegressor(n_estimators=200, max_depth=5, random_state=42)
    if len(feat) >= 2:
        model.fit(X, y)
    else:
        model.fit(pd.DataFrame([[0] * len(FEATURE_COLS)] * 2, columns=FEATURE_COLS), [0, 0])
    return model


def _topsis(df: pd.DataFrame, criteria_cols, weights, benefit_flags) -> np.ndarray:
    X = df[criteria_cols].to_numpy(dtype=float)
    weights = np.array(weights, dtype=float)
    weights = weights / weights.sum()

    col_norm = np.sqrt((X ** 2).sum(axis=0))
    col_norm[col_norm == 0] = 1
    norm = X / col_norm

    weighted = norm * weights

    ideal_best = np.where(benefit_flags, weighted.max(axis=0), weighted.min(axis=0))
    ideal_worst = np.where(benefit_flags, weighted.min(axis=0), weighted.max(axis=0))

    dist_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    dist_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

    denom = dist_best + dist_worst
    denom[denom == 0] = 1
    closeness = dist_worst / denom
    return np.nan_to_num(closeness, nan=0.5)


def rank_products(
    products: Sequence[DictLike],
    transactions: Sequence[DictLike],
    today: Union[date, str, None] = None,
) -> pd.DataFrame:
    today = _to_date(today) if today is not None else date.today()

    feat = _build_features(products, transactions, today)
    if feat.empty:
        return feat

    model = _train_model(feat)
    feat = feat.copy()
    feat['predicted_sales_velocity'] = model.predict(feat[FEATURE_COLS])

    feat['expired_urgency'] = np.clip(1 - (feat['days_until_expired'] / 60), 0, 1.5)
    max_vel = feat['predicted_sales_velocity'].max() or 1
    feat['low_sales_urgency'] = 1 - (feat['predicted_sales_velocity'] / max_vel)
    feat['high_stock_urgency'] = feat['stock_to_sales_ratio'] / feat['stock_to_sales_ratio'].max()

    feat['topsis_score'] = _topsis(
        feat,
        ['expired_urgency', 'low_sales_urgency', 'high_stock_urgency'],
        weights=[0.6, 0.5, 0.4],  # Near Expired 0.6, Low Sales 0.5, High Stock 0.4
        benefit_flags=[True, True, True],
    )

    return feat.sort_values('topsis_score', ascending=False).reset_index(drop=True)


def build_mission_plan(
    products: Sequence[DictLike],
    transactions: Sequence[DictLike],
    level_number: int,
    today: Union[date, str, None] = None,
) -> Optional[dict]:
    ranked = rank_products(products, transactions, today=today)
    if ranked.empty:
        return None

    target_gmv = float(gmv_target_for_level(level_number))
    deadline_days = deadline_days_for_level(level_number)
    xp_reward = xp_reward_for_level(level_number)

    # Prioritaskan produk yang harganya masih di bawah target GMV supaya
    # target quantity masuk akal (> 1 unit bila memungkinkan).
    fits_cap = ranked[ranked['price'] <= target_gmv]
    chosen = fits_cap.iloc[0] if not fits_cap.empty else ranked.iloc[0]

    target_quantity = target_quantity_for_gmv(target_gmv, chosen['price'])

    return {
        'product_id': int(chosen['product_id']),
        'product_name': chosen['product_name'],
        'price': float(chosen['price']),
        'target_gmv': target_gmv,
        'target_quantity': target_quantity,
        'deadline_days': deadline_days,
        'xp_reward': xp_reward,
        'predicted_sales_velocity': round(float(chosen['predicted_sales_velocity']), 2),
        'topsis_score': round(float(chosen['topsis_score']), 3),
    }


if __name__ == '__main__':
    demo_products = [
        {"product_id": 1, "product_name": "Kopi Sachet", "price": 2500,
         "current_stock": 300, "expired_date": "2026-08-01"},
        {"product_id": 2, "product_name": "Minyak Goreng 1L", "price": 18000,
         "current_stock": 20, "expired_date": None},
        {"product_id": 3, "product_name": "Beras 5kg", "price": 65000,
         "current_stock": 15, "expired_date": "2027-01-01"},
        {"product_id": 4, "product_name": "Mie Instan", "price": 3000,
         "current_stock": 500, "expired_date": "2026-07-20"},
    ]
    demo_transactions = [
        {"product_id": 1, "quantity": 10, "transaction_date": "2026-07-05"},
        {"product_id": 1, "quantity": 8, "transaction_date": "2026-06-28"},
        {"product_id": 4, "quantity": 20, "transaction_date": "2026-07-06"},
        {"product_id": 4, "quantity": 15, "transaction_date": "2026-06-25"},
        {"product_id": 2, "quantity": 1, "transaction_date": "2026-06-10"},
    ]

    print("=== Ranking produk (AI Priority Engine) ===")
    ranked = rank_products(demo_products, demo_transactions, today="2026-07-10")
    print(ranked[['product_id', 'product_name', 'price', 'days_until_expired',
                  'predicted_sales_velocity', 'topsis_score']].to_string(index=False))

    print("\n=== Contoh mission plan buat user level 3 ===")
    plan = build_mission_plan(demo_products, demo_transactions, level_number=3, today="2026-07-10")
    for k, v in plan.items():
        print(f"  {k}: {v}")
