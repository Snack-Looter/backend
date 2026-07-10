from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.gamification.urls")),
    path("api/", include("apps.catalog.urls")),
    path("api/", include("apps.transactions.urls")),
    path("api/chat/", include("apps.chatbot.urls")),
]
