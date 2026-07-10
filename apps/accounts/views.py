from rest_framework import generics, permissions
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, Province, City, Koperasi
from .serializers import RegisterSerializer, ProfileSerializer, ChangePasswordSerializer
from .geo_serializers import ProvinceSerializer, CitySerializer, KoperasiSerializer


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/"""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/  — pakai email sebagai USERNAME_FIELD."""
    permission_classes = [permissions.AllowAny]


class LogoutView(APIView):
    """POST /api/auth/logout/  — blacklist refresh token."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({"error": "Token tidak valid"}, status=400)
        return Response(status=200)


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/profile/"""
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/  body: { "old_password", "new_password" }"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response(status=204)


class ProvinceListView(ListAPIView):
    """GET /api/auth/provinces/"""
    queryset = Province.objects.all().order_by("province_name")
    serializer_class = ProvinceSerializer
    permission_classes = [permissions.AllowAny]


class CityListView(ListAPIView):
    """GET /api/auth/provinces/<province_id>/cities/"""
    serializer_class = CitySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return City.objects.filter(province_id=self.kwargs["province_id"]).order_by("city_name")


class KoperasiListView(ListAPIView):
    """GET /api/auth/cities/<city_id>/koperasi/"""
    serializer_class = KoperasiSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Koperasi.objects.filter(city_id=self.kwargs["city_id"]).order_by("koperasi_name")
