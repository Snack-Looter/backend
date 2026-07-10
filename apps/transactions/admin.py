from django.contrib import admin
from .models import Transaction, TransactionDetail


class TransactionDetailInline(admin.TabularInline):
    model = TransactionDetail
    extra = 0
    readonly_fields = ["total_price"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["transaction_id", "transaction_date", "cashier", "mission", "total_amount"]
    list_filter = ["mission"]
    inlines = [TransactionDetailInline]
