from rest_framework import serializers
from .models import User, Player, Role, PlayerRole, Koperasi


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    invite_code = serializers.CharField(
        required=False, allow_blank=True, write_only=True,
        help_text="Username pemain lain yang mengundang (opsional, bonus XP untuk keduanya).",
    )
    koperasi_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = User
        fields = [
            "user_name", "name", "gender", "phone_number", "email",
            "password", "invite_code", "koperasi_id",
        ]

    def validate_koperasi_id(self, value):
        if not Koperasi.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Koperasi tidak ditemukan.")
        return value

    def create(self, validated_data):
        koperasi_id = validated_data.pop("koperasi_id")
        invite_code = validated_data.pop("invite_code", None)
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, koperasi_id=koperasi_id, **validated_data)

        referred_by = None
        if invite_code:
            referred_by = User.objects.filter(user_name=invite_code).first()

        player = Player.objects.create(
            user=user,
            total_xp=50,  # starting XP [TUNABLE]
            referred_by=referred_by,
        )
        if referred_by is not None:
            # bonus referral [TUNABLE: +25 masing-masing]
            player.total_xp += 25
            player.save(update_fields=["total_xp"])
            ref_player = getattr(referred_by, "player", None)
            if ref_player:
                ref_player.total_xp += 25
                ref_player.save(update_fields=["total_xp"])
        return user


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["role_id", "role_name", "description"]


class PlayerRoleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.role_name", read_only=True)

    class Meta:
        model = PlayerRole
        fields = [
            "role_id", "role_name", "current_level_number", "role_xp",
            "mission_completed_count", "mission_failed_count",
        ]


class ProfileSerializer(serializers.ModelSerializer):
    total_xp = serializers.IntegerField(source="player.total_xp", read_only=True)
    invite_code = serializers.CharField(source="user_name", read_only=True)
    roles = PlayerRoleSerializer(source="player.player_roles", many=True, read_only=True)
    koperasi_name = serializers.CharField(source="koperasi.koperasi_name", read_only=True)
    top_role = serializers.SerializerMethodField()
    battle_pass_tier = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "user_id", "name", "user_name", "gender", "phone_number", "email",
            "profile_picture", "created_at", "total_xp", "invite_code", "roles",
            "koperasi_name", "top_role", "battle_pass_tier",
        ]

    def get_top_role(self, obj):
        # "Top role" = role dengan level tertinggi; seri dipecahkan oleh role_xp.
        top = obj.player.player_roles.order_by("-current_level_number", "-role_xp").first()
        if top is None:
            return None
        return {
            "role_id": top.role_id,
            "role_name": top.role.role_name,
            "current_level_number": top.current_level_number,
        }

    def get_battle_pass_tier(self, obj):
        from apps.gamification.services import get_battle_pass_status
        return get_battle_pass_status(obj.player)["current_tier"]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        if not self.context["user"].check_password(value):
            raise serializers.ValidationError("Password lama salah.")
        return value
