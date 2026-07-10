from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, LoginView, LogoutView, ProfileView, ChangePasswordView,
    ProvinceListView, CityListView, KoperasiListView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("login/refresh/", TokenRefreshView.as_view(), name="login-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("provinces/", ProvinceListView.as_view(), name="province-list"),
    path("provinces/<int:province_id>/cities/", CityListView.as_view(), name="city-list"),
    path("cities/<int:city_id>/koperasi/", KoperasiListView.as_view(), name="koperasi-list"),
]
