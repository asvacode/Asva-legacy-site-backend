from django.contrib.auth import get_user_model
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserProfile
from .serializers import ReferenceSerializer, RegisterSerializer, EmailOrUsernameTokenSerializer


User = get_user_model()


class AuthApiRootView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        return Response(
            {
                "detail": "ASVA auth API",
                "endpoints": {
                    "register": {"method": "POST", "url": "/api/auth/register"},
                    "login": {"method": "POST", "url": "/api/auth/login"},
                    "logout": {"method": "POST", "url": "/api/auth/logout"},
                    "token_refresh": {"method": "POST", "url": "/api/auth/token/refresh"},
                },
            }
        )


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        profile = user.profile
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "reference_code": profile.reference_code,
            },
            status=status.HTTP_201_CREATED,
        )


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile = UserProfile.objects.get(user=request.user)
        serializer = ReferenceSerializer({"reference_code": profile.reference_code, "is_active": profile.is_active, "phone_number": profile.phone_number})
        return Response(serializer.data)


class EmailOrUsernameTokenView(TokenObtainPairView):
    serializer_class = EmailOrUsernameTokenSerializer


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"detail": "Logged out successfully."},
            status=status.HTTP_205_RESET_CONTENT
        )