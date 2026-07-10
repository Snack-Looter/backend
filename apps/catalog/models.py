from django.db import models


class Product(models.Model):
    product_id = models.BigAutoField(primary_key=True)
    product_name = models.CharField(max_length=150)
    category = models.CharField(max_length=50, blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    current_stock = models.PositiveIntegerField(default=0)
    expired_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kopdes"."product'

    def __str__(self):
        return self.product_name
