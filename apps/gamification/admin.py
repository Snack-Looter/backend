from django.contrib import admin
from .models import Level, Mission, BattlePassMilestone, PlayerBattlePassReward


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ["role", "level_number", "gmv_target", "xp_reward", "deadline_numberdays"]
    list_filter = ["role"]


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    """Tier-1 petugas: review misi + verifikasi (audit) — lihat App Flow Spec."""
    list_display = [
        "mission_id", "player", "role", "status", "product_name_snapshot",
        "target_quantity", "target_gmv", "deadline_date", "created_at",
    ]
    list_filter = ["status", "role"]
    search_fields = ["player__user__user_name", "product_name_snapshot"]


@admin.register(BattlePassMilestone)
class BattlePassMilestoneAdmin(admin.ModelAdmin):
    """Katalog reward — petugas edit di sini, tanpa redeploy."""
    list_display = ["milestone_id", "total_xp_threshold", "reward_description"]
    ordering = ["total_xp_threshold"]


@admin.register(PlayerBattlePassReward)
class PlayerBattlePassRewardAdmin(admin.ModelAdmin):
    """Read-only audit: reward apa saja yang sudah ter-unlock/redeem per player."""
    list_display = [
        "reward_id", "player", "reward_description_snapshot",
        "unlocked_at", "redeemed_at",
    ]
    list_filter = ["milestone"]
    search_fields = ["player__user__user_name"]
