from django.db import models
from apps.accounts.models import Player, Role


class Level(models.Model):
    level_id = models.AutoField(primary_key=True)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="levels")
    level_number = models.PositiveIntegerField()
    deadline_numberdays = models.PositiveIntegerField()
    xp_reward = models.PositiveIntegerField()
    gmv_target = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'kopquest"."level'
        constraints = [
            models.UniqueConstraint(fields=["role", "level_number"], name="uq_level_role_number"),
        ]

    def __str__(self):
        return f"{self.role.role_name} - Level {self.level_number}"


class Mission(models.Model):
    STATUS_ONGOING = "ongoing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_ONGOING, "Ongoing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    mission_id = models.BigAutoField(primary_key=True)
    player = models.ForeignKey(
        Player, db_column="user_id", on_delete=models.CASCADE, related_name="missions",
    )
    # Didenormalisasi dari level.role: dibutuhkan supaya constraint "satu mission
    # aktif per role" bisa ditegakkan di level DB, dan supaya query "mission aktif
    # di role X" tidak perlu join lewat Level.
    role = models.ForeignKey(Role, on_delete=models.RESTRICT, related_name="missions")
    level = models.ForeignKey(Level, on_delete=models.RESTRICT, related_name="missions")

    # Snapshot produk saat mission digenerate (bukan live FK ke catalog.Product)
    product_id_snapshot = models.BigIntegerField()
    product_name_snapshot = models.CharField(max_length=150)
    product_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)

    target_quantity = models.PositiveIntegerField()
    target_gmv = models.DecimalField(max_digits=12, decimal_places=2)
    deadline_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ONGOING)

    # Running counter, bertambah tiap transaksi POS tervalidasi masuk (lihat
    # ValidateReferralTransactionView) — hanya dari baris yang produknya cocok
    # dengan product_id_snapshot. Verify Progress tinggal baca ini.
    current_gmv = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_quantity = models.PositiveIntegerField(default=0)

    # Identitas transaksi POS untuk mission ini. Hanya "hidup" (bisa dipakai
    # kasir) selama status masih ongoing — lihat query di services.py.
    referral_code = models.CharField(max_length=5, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'kopquest"."mission'
        constraints = [
            # Satu mission ongoing per (player, role) — pengguna boleh punya
            # beberapa mission aktif bersamaan selama beda role.
            models.UniqueConstraint(
                fields=["player", "role"],
                condition=models.Q(status="ongoing"),
                name="uq_mission_one_active_per_player_role",
            ),
        ]

    def __str__(self):
        return f"Mission#{self.mission_id} - {self.player.user.user_name} ({self.status})"


class BattlePassMilestone(models.Model):
    """Katalog reward battle pass (data referensi, editable via admin)."""
    milestone_id = models.AutoField(primary_key=True)
    total_xp_threshold = models.PositiveIntegerField(unique=True)
    reward_description = models.CharField(max_length=255)

    class Meta:
        db_table = 'kopquest"."battle_pass_milestone'
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_xp_threshold__gt=0),
                name="chk_milestone_threshold_positive",
            ),
        ]

    def __str__(self):
        return f"XP {self.total_xp_threshold} - {self.reward_description}"


class PlayerBattlePassReward(models.Model):
    """Status unlock/redeem reward per player (stateful, sama pola dengan Mission snapshot)."""
    reward_id = models.BigAutoField(primary_key=True)
    player = models.ForeignKey(
        Player, db_column="user_id", on_delete=models.CASCADE, related_name="battle_pass_rewards",
    )
    milestone = models.ForeignKey(
        BattlePassMilestone, on_delete=models.RESTRICT, related_name="player_rewards",
    )
    reward_description_snapshot = models.CharField(max_length=255)
    unlocked_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'kopquest"."player_battle_pass_reward'
        constraints = [
            models.UniqueConstraint(fields=["player", "milestone"], name="uq_player_milestone"),
        ]

    def __str__(self):
        return f"{self.player.user.user_name} - {self.reward_description_snapshot}"
