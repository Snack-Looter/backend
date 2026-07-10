from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Tier-1 petugas: kelola data produk & stok — fuel untuk mission generator."""
    list_display = ["product_id", "product_name", "category", "price", "current_stock", "expired_date"]
    list_editable = ["current_stock", "price"]
    search_fields = ["product_name", "category"]
