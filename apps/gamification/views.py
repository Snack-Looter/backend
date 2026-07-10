from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, PlayerRole
from .models import Level, Mission
from .serializers import LevelSummarySerializer, MissionSerializer, BattlePassMilestoneSerializer
from . import services


class RoleListView(APIView):
    """GET /api/roles/ — daftar role tersedia untuk New Mission dropdown."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        roles = Role.objects.all().values("role_id", "role_name", "description")
        return Response(list(roles))


class RoleProgressSummaryView(APIView):
    """GET /api/roles/{role_id}/summary/ — ringkasan progress sebelum Start Mission."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, role_id):
        player = request.user.player
        role = Role.objects.filter(pk=role_id).first()
        if role is None:
            return Response({"error": "Role tidak ditemukan"}, status=404)

        player_role = services.get_or_create_player_role(player, role)
        completed_in_cycle = player_role.mission_completed_count % services.MISSIONS_PER_LEVEL
        remaining = services.MISSIONS_PER_LEVEL - completed_in_cycle

        data = {
            "role_id": role.role_id,
            "role_name": role.role_name,
            "current_level_number": player_role.current_level_number,
            "role_xp": player_role.role_xp,
            "mission_completed_count": player_role.mission_completed_count,
            "mission_failed_count": player_role.mission_failed_count,
            "missions_remaining_to_next_level": remaining,
        }
        return Response(LevelSummarySerializer(data).data)


class ActiveMissionForRoleView(APIView):
    """
    GET /api/roles/{role_id}/active-mission/
    Dipakai Home untuk menentukan State A (No Active Mission → Find Mission)
    vs State B (Active Mission → tombol Mission Detail) per role, tanpa FE
    perlu tahu mission_id lebih dulu.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, role_id):
        role = Role.objects.filter(pk=role_id).first()
        if role is None:
            return Response({"error": "Role tidak ditemukan"}, status=404)

        mission = services.get_active_mission(request.user.player, role)
        if mission is None:
            return Response({"active_mission": None})
        return Response({"active_mission": MissionSerializer(mission).data})


class GenerateMissionView(APIView):
    """POST /api/missions/generate/  body: { "role_id": <int> }"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        role_id = request.data.get("role_id")
        role = Role.objects.filter(pk=role_id).first()
        if role is None:
            return Response({"error": "Role tidak ditemukan"}, status=404)
        try:
            mission = services.generate_mission(request.user.player, role)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        return Response(MissionSerializer(mission).data, status=status.HTTP_201_CREATED)


class MissionDetailView(APIView):
    """GET /api/missions/{id}/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, mission_id):
        mission = Mission.objects.filter(
            pk=mission_id, player=request.user.player
        ).first()
        if mission is None:
            return Response({"error": "Mission tidak ditemukan"}, status=404)
        return Response(MissionSerializer(mission).data)


class VerifyProgressView(APIView):
    """
    POST /api/missions/{id}/verify/
    body opsional: { "force_success": true|false }

    Tanpa force_success: verifikasi natural (cek current_gmv/current_quantity
    dari transaksi POS riil). Dengan force_success: override tombol demo
    "Demo Sukses"/"Demo Gagal" di Mission Detail — lihat services.verify_progress.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, mission_id):
        mission = Mission.objects.filter(
            pk=mission_id, player=request.user.player
        ).first()
        if mission is None:
            return Response({"error": "Mission tidak ditemukan"}, status=404)

        force_success = request.data.get("force_success")
        if force_success is not None:
            force_success = bool(force_success)

        try:
            mission = services.verify_progress(mission, force_success=force_success)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        return Response(MissionSerializer(mission).data)


class MissionHistoryView(APIView):
    """GET /api/missions/history/ — Task History (Progress Tracker)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        missions = Mission.objects.filter(
            player=request.user.player
        ).exclude(status=Mission.STATUS_ONGOING).order_by("-created_at")
        return Response(MissionSerializer(missions, many=True).data)


class RoleProgressListView(APIView):
    """GET /api/progress/roles/ — tab Role Progress di Progress Tracker."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        player = request.user.player
        player_roles = PlayerRole.objects.filter(player=player).select_related("role")
        data = []
        for pr in player_roles:
            completed_in_cycle = pr.mission_completed_count % services.MISSIONS_PER_LEVEL
            data.append({
                "role_id": pr.role.role_id,
                "role_name": pr.role.role_name,
                "current_level_number": pr.current_level_number,
                "role_xp": pr.role_xp,
                "mission_completed_count": pr.mission_completed_count,
                "mission_failed_count": pr.mission_failed_count,
                "missions_remaining_to_next_level": services.MISSIONS_PER_LEVEL - completed_in_cycle,
            })
        return Response({
            "total_xp": player.total_xp,
            "roles": LevelSummarySerializer(data, many=True).data,
        })


class BattlePassStatusView(APIView):
    """
    GET /api/progress/battle-pass/
    Dipakai tab Battle Pass di Progress DAN halaman Reward (datanya sama) —
    total XP, tier saat ini, next reward, dan roadmap lengkap semua milestone.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        player = request.user.player
        data = services.get_battle_pass_status(player)
        next_milestone = data["next_milestone"]

        roadmap = BattlePassMilestoneSerializer(
            data["milestones"], many=True, context={"unlocked_map": data["unlocked_map"]},
        ).data

        return Response({
            "total_xp": data["total_xp"],
            "current_tier": data["current_tier"],
            "next_reward": next_milestone.reward_description if next_milestone else None,
            "xp_required_to_next": data["xp_required_to_next"],
            "roadmap": roadmap,
        })
