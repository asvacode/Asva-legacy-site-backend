from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from phonenumber_field.serializerfields import PhoneNumberField

from .models import ExistingMember, UserProfile
from .utils import generate_reference_code, normalize_nigerian_phone_number

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
        user.is_active = True  # inactive until payment confirmed by admin
        user.save()

        # User profile is_active is set to false during sign up until payment has been completed
        UserProfile.objects.create(user=user, reference_code=generate_reference_code(), phone_number=validated_data.get("phone_number"))

        return user


class ReferenceSerializer(serializers.Serializer):
    reference_code = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField()
    phone_number = serializers.CharField()


class ExistingMemberActivationSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_phone_number(self, value):
        try:
            return normalize_nigerian_phone_number(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class EmailOrUsernameTokenSerializer(TokenObtainPairSerializer):
    username = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False, write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].required = False

    def validate(self, attrs):
        login_input = attrs.get("phone_number") or attrs.get("username")
        if not login_input:
            raise serializers.ValidationError({"username": "This field is required."})

        explicit_phone = bool(attrs.get("phone_number"))
        if explicit_phone or "@" not in login_input:
            try:
                normalized_phone = normalize_nigerian_phone_number(login_input)
            except ValueError as exc:
                if explicit_phone:
                    raise serializers.ValidationError({"phone_number": str(exc)}) from exc
            else:
                member = ExistingMember.objects.select_related("user").filter(
                    phone_number=normalized_phone
                ).first()
                if member is not None:
                    if (
                        member.user_id is None
                        or not member.user.is_active
                        or not UserProfile.objects.filter(
                            user=member.user,
                            phone_number=normalized_phone,
                            is_active=True,
                        ).exists()
                    ):
                        raise AuthenticationFailed(
                            "No active account found with the given credentials."
                        )
                    attrs["username"] = member.user.username
                elif explicit_phone:
                    raise AuthenticationFailed(
                        "No active account found with the given credentials."
                    )

        if "@" in login_input:
            try:
                user = User.objects.get(email=login_input)
                attrs["username"] = user.username
            except User.DoesNotExist:
                attrs["username"] = login_input

        attrs.pop("phone_number", None)
        return super().validate(attrs)