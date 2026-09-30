from __future__ import annotations

from django.conf import settings
from django.db import models


class PaymentClaim(models.Model):
    class Status(models.TextChoices):
        PENDING_REVIEW = "PENDING_REVIEW", "Pending review"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_claims")
    reference_code = models.CharField(max_length=16, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING_REVIEW, db_index=True)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.reference_code} - {self.amount} ({self.status})"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"
        REVERSED = "REVERSED", "Reversed"

    class PaymentType(models.TextChoices):
        CARD = "card", "Card"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        USSD = "ussd", "USSD"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        QR = "qr", "QR"
        BANK = "bank", "BANK"
        OTHER = "OTHER", "Other"
    
    class Purpose(models.TextChoices):
        ACCOUNT_CREATION = "ACCOUNT_CREATION", "Account Creation"
        DEV_CENTER_BOOKING = "DEV_CENTER_BOOKING", "Dev Center Booking"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
    idempotency_key = models.CharField(max_length=250, unique=True)
    purpose = models.CharField(max_length=32, choices=Purpose.choices, null=False, default=Purpose.ACCOUNT_CREATION)
    paystack_access_code = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.paystack_reference} - {self.amount} {self.currency} ({self.status})"


class AdminNotification(models.Model):
    class Type(models.TextChoices):
        PAYMENT_CLAIM_SUBMITTED = "PAYMENT_CLAIM_SUBMITTED", "Payment claim submitted"
        PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED", "Payment confirmed"
        PAYMENT_REJECTED = "PAYMENT_REJECTED", "Payment rejected"

    type = models.CharField(max_length=64, choices=Type.choices)
    reference_code = models.CharField(max_length=16, db_index=True)
    claim = models.ForeignKey(PaymentClaim, on_delete=models.CASCADE, related_name="notifications")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.type} - {self.reference_code}"

