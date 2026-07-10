from rest_framework import serializers, permissions
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["product_id", "product_name", "category", "price", "current_stock", "expired_date"]


class ProductListView(ListAPIView):
    """GET /api/products/ — dipakai petugas untuk kelola stok (Tier 1 admin)."""
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]


class ProductDetailView(RetrieveUpdateAPIView):
    """GET/PATCH /api/products/{id}/"""
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
