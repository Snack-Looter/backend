import math
import random
import string
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import PlayerRole
from apps.catalog.models import Product
from .models import Level, Mission, BattlePassMilestone, PlayerBattlePassReward

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


def pick_product_for_mission() -> Product:
    """
    MVP: pilih produk secara sederhana (mis. stok tersedia, acak).
    TODO roadmap: AI Mission Generator berbasis data real (stok, expiry, sales trend).
    """
    candidates = Product.objects.filter(current_stock__gt=0)
    if not candidates.exists():
        raise ValueError("Tidak ada produk dengan stok tersedia untuk membuat mission.")
    return random.choice(list(candidates))


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

    level = Level.objects.filter(role=role, level_number=level_number).first()
    if level is None:
        raise ValueError(f"Konfigurasi Level {level_number} untuk role {role.role_name} belum tersedia.")

    product = pick_product_for_mission()
    target_quantity = math.ceil(float(level.gmv_target) / float(product.price))
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
