from django.db import models
from apps.accounts.models import User
from apps.catalog.models import Product
from apps.gamification.models import Mission


class Transaction(models.Model):
    transaction_id = models.BigAutoField(primary_key=True)
    transaction_date = models.DateTimeField(auto_now_add=True)
    cashier = models.ForeignKey(
        User, db_column="cashier_user_id", on_delete=models.RESTRICT, related_name="transactions",
    )
    # Terisi kalau transaksi ini divalidasi lewat Referral Code (lihat
    # ValidateReferralTransactionView) — null berarti penjualan biasa yang
    # tidak terkait mission manapun.
    mission = models.ForeignKey(
        Mission, null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions",
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = 'kopdes"."transaction'

    def __str__(self):
        return f"TRX#{self.transaction_id}"


class TransactionDetail(models.Model):
    detail_id = models.BigAutoField(primary_key=True)
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="details",
    )
    product = models.ForeignKey(Product, on_delete=models.RESTRICT, related_name="transaction_details")
    product_name = models.CharField(max_length=150)  # snapshot
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)  # snapshot
    quantity = models.PositiveIntegerField()
    total_price = models.GeneratedField(
        expression=models.F("quantity") * models.F("unit_price"),
        output_field=models.DecimalField(max_digits=12, decimal_places=2),
        db_persist=True,
    )

    class Meta:
        db_table = 'kopdes"."transaction_detail'

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"
