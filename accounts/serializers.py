from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from phonenumber_field.serializerfields import PhoneNumberField

from .models import UserProfile
from .utils import generate_reference_code

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    phone_number = PhoneNumberField(region='NG', allow_blank=True, required=False)

    class Meta:
        model = User
        fields = ["username", "email", "password", "phone_number"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(username=validated_data['username'], email=validated_data['email'])
        user.set_password(password)
        user.is_active = False  # inactive until payment confirmed by admin
        user.save()

        UserProfile.objects.create(user=user, reference_code=generate_reference_code(), phone_number=validated_data.get("phone_number"))

        return user


class ReferenceSerializer(serializers.Serializer):
    reference_code = serializers.CharField(read_only=True)


class EmailOrUsernameTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        login_input = attrs.get("username")
        if "@" in login_input:
            try:
                user = User.objects.get(email=login_input)
                attrs["username"] = user.username
            except User.DoesNotExist:
                pass
        return super().validate(attrs)