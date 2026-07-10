import logging
import random
import string
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import PlayerRole
from apps.catalog.models import Product
from . import product_targeting_engine as engine
from .models import Level, Mission, BattlePassMilestone, PlayerBattlePassReward

logger = logging.getLogger(__name__)

MISSIONS_PER_LEVEL = 5  # 5 misi Completed untuk naik level (role progression)
REFERRAL_CODE_ALPHABET = string.ascii_uppercase + string.digits
REFERRAL_CODE_LENGTH = 5


def generate_referral_code() -> str:
    """
    Kode identitas mission untuk validasi transaksi POS (5 karakter alfanumerik,
    unik global). Hanya "aktif" dipakai kasir selama mission masih ongoing —
    lihat filter status di endpoint validasi transaksi.
    """
    for _ in range(20):
        code = "".join(random.choices(REFERRAL_CODE_ALPHABET, k=REFERRAL_CODE_LENGTH))
        if not Mission.objects.filter(referral_code=code).exists():
            return code
    raise RuntimeError("Gagal generate referral code unik, coba lagi.")


def get_or_create_player_role(player, role):
    player_role, _ = PlayerRole.objects.get_or_create(
        player=player, role=role,
        defaults={"current_level_number": 1},
    )
    return player_role


def check_battle_pass_unlocks(player):
    """
    Cek milestone battle pass yang baru terlewati setelah total_xp bertambah,
    lalu simpan sebagai reward ter-unlock (snapshot teks, sama pola dengan Mission).
    """
    unlocked_ids = set(
        PlayerBattlePassReward.objects.filter(player=player)
        .values_list("milestone_id", flat=True)
    )
    newly_unlocked = BattlePassMilestone.objects.filter(
        total_xp_threshold__lte=player.total_xp
    ).exclude(milestone_id__in=unlocked_ids)

    for milestone in newly_unlocked:
        PlayerBattlePassReward.objects.create(
            player=player, milestone=milestone,
            reward_description_snapshot=milestone.reward_description,
        )


def get_battle_pass_status(player) -> dict:
    """
    current_tier = jumlah milestone yang sudah ter-unlock (bukan konsep
    terpisah dari urutan XP — spec tidak mendefinisikan tier secara eksplisit).
    """
    milestones = list(BattlePassMilestone.objects.order_by("total_xp_threshold"))
    unlocked_map = {
        r.milestone_id: r
        for r in PlayerBattlePassReward.objects.filter(player=player)
    }
    current_tier = sum(1 for m in milestones if m.milestone_id in unlocked_map)
    next_milestone = next((m for m in milestones if m.total_xp_threshold > player.total_xp), None)

    return {
        "total_xp": player.total_xp,
        "current_tier": current_tier,
        "next_milestone": next_milestone,
        "xp_required_to_next": (
            next_milestone.total_xp_threshold - player.total_xp if next_milestone else None
        ),
        "milestones": milestones,
        "unlocked_map": unlocked_map,
    }


def _rank_products_with_engine(candidates: list[Product], target_gmv: float):
    """
    Feed data ORM ke AI Priority Engine (RandomForest + TOPSIS, lihat
    product_targeting_engine.py) lalu kembalikan product_id terpilih:
    peringkat teratas yang harganya <= target GMV (supaya target quantity
    masuk akal), atau peringkat teratas mutlak kalau semuanya di atas cap.
    """
    # Impor lokal untuk memutus circular import:
    # transactions.models -> gamification.models (Mission).
    from apps.transactions.models import TransactionDetail

    today = timezone.now().date()
    products = [
        {
            "product_id": p.product_id,
            "product_name": p.product_name,
            "price": p.price,
            "current_stock": p.current_stock,
            "expired_date": p.expired_date,
        }
        for p in candidates
    ]
    # Engine hanya memakai histori 60 hari — batasi query-nya sekalian.
    cutoff = today - timedelta(days=60)
    transactions = list(
        TransactionDetail.objects.filter(transaction__transaction_date__date__gte=cutoff)
        .values("product_id", "quantity")
        .annotate(transaction_date=F("transaction__transaction_date"))
    )

    ranked = engine.rank_products(products, transactions, today=today)
    fits_cap = ranked[ranked["price"] <= float(target_gmv)]
    chosen = fits_cap.iloc[0] if not fits_cap.empty else ranked.iloc[0]
    return int(chosen["product_id"])


def pick_product_for_mission(target_gmv: float) -> Product:
    """
    AI Mission Generator: pilih produk yang paling butuh didorong penjualannya
    (mendekati expired, penjualan diprediksi rendah, stok menumpuk).
    Kalau engine gagal (data aneh, dsb.) jatuh ke pilihan acak supaya
    Generate Mission tidak pernah mati hanya karena ranking bermasalah.
    """
    candidates = list(Product.objects.filter(current_stock__gt=0))
    if not candidates:
        raise ValueError("Tidak ada produk dengan stok tersedia untuk membuat mission.")

    try:
        chosen_id = _rank_products_with_engine(candidates, target_gmv)
        return next(p for p in candidates if p.product_id == chosen_id)
    except Exception:
        logger.exception("AI Priority Engine gagal, fallback ke pilihan acak.")
        return random.choice(candidates)


def _expire_if_overdue(mission: Mission) -> Mission:
    """
    Lazy check: kalau mission masih ongoing tapi deadline sudah lewat, tandai
    failed saat ini juga. Dipanggil tiap kali mission diakses/diverifikasi —
    tidak butuh scheduler/cron terpisah.
    """
    if mission.status == Mission.STATUS_ONGOING and mission.deadline_date < timezone.now().date():
        mission.status = Mission.STATUS_FAILED
        mission.completed_at = timezone.now()
        mission.save(update_fields=["status", "completed_at"])

        player_role = get_or_create_player_role(mission.player, mission.role)
        player_role.mission_failed_count += 1
        player_role.save(update_fields=["mission_failed_count", "updated_at"])
        # failed TIDAK mengurangi level/XP (sesuai spesifikasi progression)
    return mission


def get_active_mission(player, role) -> Mission | None:
    mission = Mission.objects.filter(
        player=player, role=role, status=Mission.STATUS_ONGOING
    ).select_related("level", "role").first()
    if mission is None:
        return None
    mission = _expire_if_overdue(mission)
    return mission if mission.status == Mission.STATUS_ONGOING else None


def generate_mission(player, role) -> Mission:
    """
    Generate mission baru untuk player pada role tertentu.
    Aturan 'One Active Mission per Role' ditegakkan oleh unique constraint DB
    (uq_mission_one_active_per_player_role) — cek eksplisit di sini untuk
    pesan error yang jelas ke FE. Role lain milik player yang sama tidak
    terpengaruh, sesuai spesifikasi multi-role concurrent mission.
    """
    if get_active_mission(player, role) is not None:
        raise ValueError(
            f"Masih ada mission aktif di role {role.role_name}. "
            "Selesaikan dulu sebelum membuat mission baru di role ini."
        )

    player_role = get_or_create_player_role(player, role)
    level_number = player_role.current_level_number

    # Level 1-10 sudah di-seed di db/schema.sql dengan rumus yang sama;
    # get_or_create menjamin level di atasnya ikut rumus engine juga tanpa
    # perlu seeding manual.
    level, _ = Level.objects.get_or_create(
        role=role,
        level_number=level_number,
        defaults={
            "xp_reward": engine.xp_reward_for_level(level_number),
            "gmv_target": engine.gmv_target_for_level(level_number),
            "deadline_numberdays": engine.deadline_days_for_level(level_number),
        },
    )

    product = pick_product_for_mission(float(level.gmv_target))
    # Floor min 1 unit (spec engine) — GMV jadi syarat pengikat, bukan quantity.
    target_quantity = engine.target_quantity_for_gmv(float(level.gmv_target), float(product.price))
    deadline_date = timezone.now().date() + timedelta(days=level.deadline_numberdays)

    mission = Mission.objects.create(
        player=player,
        role=role,
        level=level,
        product_id_snapshot=product.product_id,
        product_name_snapshot=product.product_name,
        product_price_snapshot=product.price,
        target_quantity=target_quantity,
        target_gmv=level.gmv_target,
        deadline_date=deadline_date,
        status=Mission.STATUS_ONGOING,
        referral_code=generate_referral_code(),
    )
    return mission


@transaction.atomic
def verify_progress(mission: Mission) -> Mission:
    """
    Hitung progress dari transaksi POS riil yang sudah tervalidasi lewat
    Referral Code (current_gmv/current_quantity di-update real-time oleh
    ValidateReferralTransactionView tiap transaksi masuk — lihat
    apps/transactions/views.py). Fungsi ini hanya mengecek apakah target
    sudah tercapai, dan menandai failed kalau deadline sudah lewat.
    """
    if mission.status != Mission.STATUS_ONGOING:
        raise ValueError("Mission ini sudah tidak berstatus ongoing.")

    mission = _expire_if_overdue(mission)
    if mission.status == Mission.STATUS_FAILED:
        return mission

    target_reached = (
        mission.current_gmv >= mission.target_gmv
        and mission.current_quantity >= mission.target_quantity
    )
    if not target_reached:
        return mission

    mission.status = Mission.STATUS_COMPLETED
    mission.completed_at = timezone.now()
    mission.save(update_fields=["status", "completed_at"])

    player_role = get_or_create_player_role(mission.player, mission.role)
    xp_reward = mission.level.xp_reward
    player_role.role_xp += xp_reward
    player_role.mission_completed_count += 1
    if player_role.mission_completed_count % MISSIONS_PER_LEVEL == 0:
        player_role.current_level_number += 1
    player_role.save()

    mission.player.total_xp += xp_reward
    mission.player.save(update_fields=["total_xp"])
    check_battle_pass_unlocks(mission.player)

    return mission
