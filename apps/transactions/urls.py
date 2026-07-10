from django.urls import path
from .views import TransactionListCreateView, ValidateReferralTransactionView

urlpatterns = [
    path("transactions/", TransactionListCreateView.as_view(), name="transaction-list-create"),
    path("transactions/validate-referral/", ValidateReferralTransactionView.as_view(), name="transaction-validate-referral"),
]
