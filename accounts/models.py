from __future__ import annotations

from django.conf import settings
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    reference_code = models.CharField(max_length=32, unique=True, db_index=True)
    phone_number = PhoneNumberField(blank=True, region="NG")

    def __str__(self) -> str:
        return f"{self.user.username} ({self.reference_code})"

