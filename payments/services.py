import hashlib
import hmac
import logging
import uuid
from decimal import Decimal

from accounts.models import UserProfile

import requests
from asva_backend.settings import PAYSTACK_SECRET_KEY
from django.utils.dateparse import parse_datetime
from django.db import IntegrityError, transaction
from .utils import translate_paystack_status

from .models import Payment

logger = logging.getLogger(__name__)

PAYSTACK_BASE_URL = "https://api.paystack.co"
PAYSTACK_TIMEOUT = 20

# ---------------- Exceptions -------------------
class PaymentError(Exception):
    """Base error for payment problems. Views map status_code to the response."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class PaystackError(PaymentError):
    """Paystack was unreachable or rejected the request."""

    def __init__(self, message):
        super().__init__(message, status_code=502)


# --------------- Paystack Client --------------------
def to_subunit(amount: Decimal) -> int:
    """Convert a major-unit amount (NGN) to kobo."""
    return int((amount * 100).quantize(Decimal("1")))


def _paystack_request(method, path, **kwargs):
    try:
        response = requests.request(
            method,
            f"{PAYSTACK_BASE_URL}{path}",
            headers={
                "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=PAYSTACK_TIMEOUT,
            **kwargs,
        )
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.exception("Paystack request failed: %s %s", method, path)
        raise PaystackError("Could not reach Paystack. Try again.") from exc

    if response.status_code != 200 or not body.get("status"):
        raise PaystackError(body.get("message", "Paystack request failed."))

    return body.get("data") or {}


def paystack_initialize(*, email, amount, currency, reference, channels=None):
    payload = {
        "email": email,
        "amount": to_subunit(amount),
        "currency": currency,
        "reference": reference,
    }
    if channels:
        payload["channels"] = channels
    return _paystack_request("POST", "/transaction/initialize", json=payload)


def paystack_verify(reference: str):
    return _paystack_request("GET", f"/transaction/verify/{reference}")


# ---------------- Verify Webhook Signature --------------------
def verify_signature(raw_body: bytes, signature: str) -> bool:
    expected = hmac.new(
        PAYSTACK_SECRET_KEY, raw_body, hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


# ------------- Payment Creation -----------------
def _get_or_create_payment(*, user, amount, currency, description, idempotency_key, purpose):
    try:
        with transaction.atomic():  # savepoint, so an IntegrityError doesn't poison an outer transaction
            payment = Payment.objects.create(
                user=user,
                amount=amount,
                currency=currency,
                status=Payment.Status.PENDING,
                description=description,
                idempotency_key=idempotency_key,
                purpose=purpose
            )
        return payment, True
    except IntegrityError:
        payment = Payment.objects.get(idempotency_key=idempotency_key)
        if payment.user_id != user.id:
            raise PaymentError("Idempotency key already in use.", status_code=409)
        return payment, False


def initialize_payment(
    *, user, email, amount, currency, description, idempotency_key, purpose, channels=None
):
    """
    Create (or fetch) the Payment for this idempotency key and make sure it has a
    Paystack access code. Returns (payment, created).
    Safe to call repeatedly with the same idempotency key.
    """
    payment, created = _get_or_create_payment(
        user=user,
        amount=amount,
        currency=currency,
        description=description,
        idempotency_key=idempotency_key,
        purpose=purpose
    )

    # Already initialized on a previous call: return it as is.
    if payment.paystack_access_code:
        return payment, created

    # A fresh reference per attempt avoids "duplicate reference" errors when an
    # earlier attempt timed out after Paystack had already created the transaction.
    data = paystack_initialize(
        email=email,
        amount=payment.amount,
        currency=payment.currency,
        reference=idempotency_key,
        channels=channels,
    )

    if not data.get("access_code"):
        raise PaystackError("Paystack response did not include an access code.")

    payment.paystack_access_code = data["access_code"]
    payment.save(update_fields=["paystack_access_code"])
    return payment, created

# ----- Verify Payment --------
def verify_payment(idempotencyKey, paystack_data=None):
    """
    Idempotently settle a payment. `paystack_data` is the transaction object from
    a signed webhook; if omitted, it is fetched from Paystack's verify endpoint.
    """
    if paystack_data is None:
        paystack_data = paystack_verify(idempotencyKey)

    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(idempotency_key=idempotencyKey)
        except Payment.DoesNotExist:
            raise PaymentError("Unknown payment reference.", status_code=404)

        # Already settled: a racing webhook/verify call does nothing.
        if payment.status == Payment.Status.SUCCESS:
            return payment

        remote_status = paystack_data.get("status")

        actual_status = translate_paystack_status(remote_status)
        if(actual_status != Payment.Status.SUCCESS):
            payment.status = actual_status
            payment.save()
            return payment

        if (
            paystack_data.get("amount") != to_subunit(payment.amount)
            or (paystack_data.get("currency") or "").upper() != payment.currency.upper()
        ):
            logger.error(
                "Payment mismatch for %s: expected %s %s, got %s %s",
                idempotencyKey,
                to_subunit(payment.amount),
                payment.currency,
                paystack_data.get("amount"),
                paystack_data.get("currency"),
            )
            raise PaymentError("Payment amount or currency mismatch.", status_code=409)

        payment.status = Payment.Status.SUCCESS
        if paystack_data.get("paid_at"):
            payment.paid_at = parse_datetime(paystack_data.get("paid_at"))
        payment.save()
        
        if(payment.status == Payment.Status.SUCCESS and payment.purpose == Payment.Purpose.ACCOUNT_CREATION):
            UserProfile.objects.filter(user=payment.user).update(is_active=True)

    return payment
