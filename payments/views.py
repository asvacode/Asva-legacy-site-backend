from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
import requests
from asva_backend.settings import PAYSTACK_SECRET_KEY
from rest_framework.response import Response
from django.contrib.auth.models import User
from rest_framework.views import APIView
from django.db import IntegrityError

from .models import AdminNotification, Payment, PaymentClaim
from .serializers import AdminNotificationSerializer, PaymentClaimCreateSerializer, PaymentClaimListSerializer
from .utils import translate_payment_channel


class CreatePaymentClaimView(generics.CreateAPIView):
    serializer_class = PaymentClaimCreateSerializer
    permission_classes = [permissions.AllowAny]  

    def perform_create(self, serializer):
        claim = serializer.save()
        AdminNotification.objects.create(
            type=AdminNotification.Type.PAYMENT_CLAIM_SUBMITTED,
            reference_code=claim.reference_code,
            claim=claim,
        )


class MyPaymentClaimsView(generics.ListAPIView):
    serializer_class = PaymentClaimListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaymentClaim.objects.filter(user=self.request.user).order_by("-created_at")


class AdminPaymentClaimsView(generics.ListAPIView):
    serializer_class = PaymentClaimListSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return PaymentClaim.objects.all().order_by("-created_at")


class AdminConfirmPaymentView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        claim = get_object_or_404(PaymentClaim, pk=pk)
        claim.status = PaymentClaim.Status.CONFIRMED
        claim.save(update_fields=["status", "updated_at"])

        # activate the user's account
        user = claim.user
        user.is_active = True
        user.save(update_fields=["is_active"])

        AdminNotification.objects.create(
            type=AdminNotification.Type.PAYMENT_CONFIRMED,
            reference_code=claim.reference_code,
            claim=claim,
        )
        return Response(status=status.HTTP_200_OK)


class AdminRejectPaymentView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        claim = get_object_or_404(PaymentClaim, pk=pk)
        update_fields = ["status", "updated_at"]
        if "admin_note" in request.data:
            claim.admin_note = request.data.get("admin_note") or ""
            update_fields.append("admin_note")
        claim.status = PaymentClaim.Status.REJECTED
        claim.save(update_fields=update_fields)
        AdminNotification.objects.create(
            type=AdminNotification.Type.PAYMENT_REJECTED,
            reference_code=claim.reference_code,
            claim=claim,
        )
        return Response(status=status.HTTP_200_OK)


class AdminNotificationsView(generics.ListAPIView):
    serializer_class = AdminNotificationSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return AdminNotification.objects.order_by("-created_at")


class AdminNotificationReadView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        notification = get_object_or_404(AdminNotification, pk=pk)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(status=status.HTTP_200_OK)
    
    
class InitiatePaystackPayment(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get("email") or (request.user.email if request.user.is_authenticated else None)
        amount = request.data.get("amount")
        
        # Validation....
        if not email or amount is None:
            return Response({"detail": "Email and amount are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        if not request.data.get("idempotency_key", None):
            return Response({"detail": "Idempotency Key is required"},status=status.HTTP_400_BAD_REQUEST)
        
        try:
            amount_decimal = Decimal(str(amount))
        except InvalidOperation:
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        
        if amount_decimal <= 0:
            return Response({"detail": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)
        
        payment_channel = request.data.get("payment_channel")        
                
        payment_type = translate_payment_channel(payment_channel)
                
        if payment_type not in {choice[0].lower() for choice in Payment.PaymentType.choices}:
            return Response({"detail": "Invalid payment type."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Create payment Object...
        try:
            payment = Payment.objects.create(**{
                "user": user,
                "amount": amount_decimal,
                "currency": request.data.get("currency", "NGN"),
                "status": Payment.Status.PENDING,
                "payment_type": payment_type,
                "description": request.data.get("description", "Payment"),
                "idempotency_key": request.data.get("idempotency_key")
            })
        except IntegrityError:
            payment = Payment.objects.get(idempotency_key=request.data.get("idempotency_key"))
            return Response({
                "message": "Payment initialized successfully.",
                "payment_id": payment.id,
                "reference": payment.paystack_reference,
                "access_code": payment.paystack_access_code
            })
        
        
        # Initialize Payment on paystack...
        payload = {
            "email": email,
            "amount": int((amount_decimal * 100).quantize(Decimal("1"))),
            "currency": "NGN",
            "channel": payment_channel,
        }

        try:
            response = requests.post(
                "https://api.paystack.co/transaction/initialize",
                json=payload,
                headers={
                    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=20,
            )
            response_data = response.json()
        except (requests.RequestException, ValueError):
            return Response({"detail": "Payment initialization failed."}, status=status.HTTP_502_BAD_GATEWAY)


        if response.status_code != 200 or not response_data.get("status"):
            payment.status = Payment.Status.FAILED
            payment.save()
            return Response(
                {"detail": response_data.get("message", "Payment initialization failed.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        paystack_data = response_data.get("data", {})
        reference = paystack_data.get("reference")
        if not reference:
            return Response({"detail": "Paystack response did not include a payment reference."}, status=status.HTTP_502_BAD_GATEWAY)

        # Update Payment object
        payment.paystack_access_code = paystack_data.get("access_code")
        payment.paystack_reference = reference
        payment.save()
        
        
        return Response(
            {
                "message": "Payment initialized successfully.",
                "payment_id": payment.id,
                "reference": payment.paystack_reference,
                "access_code": payment.paystack_access_code
            },
            status=status.HTTP_201_CREATED,
        )