from rest_framework import serializers
from .models import Level, Mission, BattlePassMilestone


class LevelSummarySerializer(serializers.Serializer):
    """Ringkasan progress role sebelum generate mission (untuk New Mission page)."""
    role_id = serializers.IntegerField()
    role_name = serializers.CharField()
    current_level_number = serializers.IntegerField()
    role_xp = serializers.IntegerField()
    mission_completed_count = serializers.IntegerField()
    mission_failed_count = serializers.IntegerField()
    missions_remaining_to_next_level = serializers.IntegerField()


class MissionSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="level.role.role_name", read_only=True)
    current_level_number = serializers.IntegerField(source="level.level_number", read_only=True)
    xp_reward = serializers.IntegerField(source="level.xp_reward", read_only=True)

    class Meta:
        model = Mission
        fields = [
            "mission_id", "role_name", "current_level_number", "xp_reward",
            "product_name_snapshot", "product_price_snapshot",
            "target_quantity", "target_gmv", "deadline_date",
            "current_quantity", "current_gmv",
            "status", "created_at", "completed_at", "referral_code",
        ]
        read_only_fields = fields


class BattlePassMilestoneSerializer(serializers.ModelSerializer):
    """Satu baris roadmap. `unlocked_at`/`redeemed_at` diambil dari context
    (unlocked_map) yang disiapkan view, supaya tidak query per-baris."""
    unlocked = serializers.SerializerMethodField()
    unlocked_at = serializers.SerializerMethodField()
    redeemed_at = serializers.SerializerMethodField()

    class Meta:
        model = BattlePassMilestone
        fields = [
            "milestone_id", "total_xp_threshold", "reward_description",
            "unlocked", "unlocked_at", "redeemed_at",
        ]

    def _reward(self, obj):
        return self.context.get("unlocked_map", {}).get(obj.milestone_id)

    def get_unlocked(self, obj):
        return self._reward(obj) is not None

    def get_unlocked_at(self, obj):
        reward = self._reward(obj)
        return reward.unlocked_at if reward else None

    def get_redeemed_at(self, obj):
        reward = self._reward(obj)
        return reward.redeemed_at if reward else None
