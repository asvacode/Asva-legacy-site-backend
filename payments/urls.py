from django.urls import path

from .views import CreatePaymentClaimView, MyPaymentClaimsView, InitiatePaystackPayment


urlpatterns = [
    path("claim", CreatePaymentClaimView.as_view(), name="payment-claim"),
    path("claims/me", MyPaymentClaimsView.as_view(), name="payment-claims-me"),
    path("initialize-payment", InitiatePaystackPayment.as_view(), name="payment-initialization")
]

