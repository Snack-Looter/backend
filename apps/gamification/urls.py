from django.urls import path
from .views import (
    RoleListView, RoleProgressSummaryView, GenerateMissionView,
    MissionDetailView, VerifyProgressView, MissionHistoryView, RoleProgressListView,
    ActiveMissionForRoleView, BattlePassStatusView,
)

urlpatterns = [
    path("roles/", RoleListView.as_view(), name="role-list"),
    path("roles/<int:role_id>/summary/", RoleProgressSummaryView.as_view(), name="role-summary"),
    path("roles/<int:role_id>/active-mission/", ActiveMissionForRoleView.as_view(), name="role-active-mission"),
    path("missions/generate/", GenerateMissionView.as_view(), name="mission-generate"),
    path("missions/history/", MissionHistoryView.as_view(), name="mission-history"),
    path("missions/<int:mission_id>/", MissionDetailView.as_view(), name="mission-detail"),
    path("missions/<int:mission_id>/verify/", VerifyProgressView.as_view(), name="mission-verify"),
    path("progress/roles/", RoleProgressListView.as_view(), name="progress-roles"),
    path("progress/battle-pass/", BattlePassStatusView.as_view(), name="progress-battle-pass"),
]
