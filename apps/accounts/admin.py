from django.contrib import admin
from .models import User, Player, Role, PlayerRole


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["user_id", "user_name", "name", "email", "is_staff", "created_at"]
    search_fields = ["user_name", "name", "email"]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["user", "total_xp", "referred_by", "created_at"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["role_id", "role_name"]


@admin.register(PlayerRole)
class PlayerRoleAdmin(admin.ModelAdmin):
    list_display = [
        "player", "role", "current_level_number", "role_xp",
        "mission_completed_count", "mission_failed_count",
    ]
    list_filter = ["role"]
