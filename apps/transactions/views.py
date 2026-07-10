from decimal import Decimal

from django.db import transaction as db_transaction
from rest_framework import serializers, permissions, status
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.gamification.models import Mission
from .models import Transaction, TransactionDetail


class InsufficientStockError(Exception):
    pass


class TransactionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionDetail
        fields = ["detail_id", "product", "product_name", "unit_price", "quantity", "total_price"]
        read_only_fields = ["detail_id", "total_price"]


class TransactionSerializer(serializers.ModelSerializer):
    details = TransactionDetailSerializer(many=True)

    class Meta:
        model = Transaction
        fields = ["transaction_id", "transaction_date", "cashier", "mission", "total_amount", "details"]
        read_only_fields = ["transaction_id", "transaction_date", "total_amount", "mission"]

    def create(self, validated_data):
        details_data = validated_data.pop("details")
        transaction = Transaction.objects.create(**validated_data)
        total = 0
        for d in details_data:
            detail = TransactionDetail.objects.create(transaction=transaction, **d)
            total += detail.quantity * detail.unit_price
        transaction.total_amount = total
        transaction.save(update_fields=["total_amount"])
        return transaction


class TransactionListCreateView(ListCreateAPIView):
    """
    GET/POST /api/transactions/
    Pencatatan transaksi umum (schema kopdes), tanpa keterkaitan mission.
    Untuk transaksi yang divalidasi lewat Referral Code (terhubung ke mission),
    pakai ValidateReferralTransactionView di bawah — bukan endpoint ini.
    """
    queryset = Transaction.objects.all().order_by("-transaction_date")
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(cashier=self.request.user)


class ReferralTransactionItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class ValidateReferralTransactionView(APIView):
    """
    POST /api/transactions/validate-referral/
    Dipakai sistem POS koperasi. Kasir input Referral Code + daftar barang;
    harga & nama produk diambil dari catalog di server (tidak dipercaya dari
    input POS) supaya tidak bisa dimanipulasi dari sisi kasir/terminal.
    body: { "referral_code": "A8F2K", "items": [{"product_id": 1, "quantity": 2}] }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        cashier = request.user
        if not cashier.is_staff:
            return Response(
                {"error": "Hanya akun petugas koperasi yang bisa memproses transaksi."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if cashier.koperasi_id is None:
            return Response(
                {"error": "Akun petugas ini belum terhubung ke koperasi manapun."},
                status=status.HTTP_403_FORBIDDEN,
            )

        code = (request.data.get("referral_code") or "").strip().upper()
        if not code:
            return Response({"error": "Referral code wajib diisi."}, status=400)

        items_serializer = ReferralTransactionItemSerializer(data=request.data.get("items") or [], many=True)
        items_serializer.is_valid(raise_exception=True)
        items = items_serializer.validated_data
        if not items:
            return Response({"error": "Minimal 1 item transaksi."}, status=400)

        mission = Mission.objects.select_related("player__user").filter(
            referral_code=code, status=Mission.STATUS_ONGOING,
        ).first()
        if mission is None:
            return Response(
                {"error": "Referral code tidak valid atau mission sudah tidak aktif."}, status=404,
            )
        if mission.player.user.koperasi_id != cashier.koperasi_id:
            return Response(
                {"error": "Mission ini terdaftar di koperasi lain, transaksi ditolak."}, status=403,
            )

        # Cek keberadaan produk dulu di luar transaksi (respons cepat untuk
        # kasus umum salah id). Stok divalidasi ULANG di bawah, di dalam lock,
        # karena angka di sini bisa basi kalau ada transaksi lain berbarengan.
        for item in items:
            if not Product.objects.filter(pk=item["product_id"]).exists():
                return Response({"error": f"Produk id={item['product_id']} tidak ditemukan."}, status=404)

        try:
            with db_transaction.atomic():
                txn = Transaction.objects.create(cashier=cashier, mission=mission)
                total = Decimal("0")
                mission_gmv_delta = Decimal("0")
                mission_qty_delta = 0
                for item in items:
                    product = Product.objects.select_for_update().get(pk=item["product_id"])
                    quantity = item["quantity"]
                    if product.current_stock < quantity:
                        raise InsufficientStockError(
                            f"Stok {product.product_name} tidak cukup (sisa {product.current_stock})."
                        )
                    TransactionDetail.objects.create(
                        transaction=txn, product=product,
                        product_name=product.product_name, unit_price=product.price,
                        quantity=quantity,
                    )
                    line_total = quantity * product.price
                    total += line_total
                    product.current_stock -= quantity
                    product.save(update_fields=["current_stock"])

                    # Hanya baris yang produknya cocok dengan snapshot mission
                    # yang menambah progress — barang lain di struk yang sama
                    # tidak relevan dengan mission ini.
                    if product.product_id == mission.product_id_snapshot:
                        mission_gmv_delta += line_total
                        mission_qty_delta += quantity

                txn.total_amount = total
                txn.save(update_fields=["total_amount"])

                if mission_gmv_delta or mission_qty_delta:
                    mission.current_gmv += mission_gmv_delta
                    mission.current_quantity += mission_qty_delta
                    mission.save(update_fields=["current_gmv", "current_quantity"])
        except InsufficientStockError as e:
            return Response({"error": str(e)}, status=400)

        return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)
