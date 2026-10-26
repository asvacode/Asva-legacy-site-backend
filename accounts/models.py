from __future__ import annotations

from django.conf import settings
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    reference_code = models.CharField(max_length=32, unique=True, db_index=True)
    phone_number = PhoneNumberField(blank=True, region="NG")
    is_active = models.BooleanField(default=False, blank=False)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.reference_code})"


class ExistingMember(models.Model):
    phone_number = PhoneNumberField(region="NG", unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="existing_member_record",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return str(self.phone_number)
