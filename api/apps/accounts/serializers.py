from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers

from .models import Role, User

# Roles a visitor may pick at sign-up. Privileged roles are only granted by admins.
SELF_SERVE_ROLES = (Role.REGISTERED, Role.STUDENT, Role.PROFESSIONAL)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "role")
        read_only_fields = fields


# Accounts the platform itself uses; nobody may register them (case-insensitive).
RESERVED_USERNAMES = frozenset({"feed-bot"})


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=SELF_SERVE_ROLES, default=Role.REGISTERED)

    class Meta:
        model = User
        fields = ("username", "email", "password", "role")

    def validate_username(self, value):
        if value.strip().lower() in RESERVED_USERNAMES:
            raise serializers.ValidationError("This username is reserved.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        password_validation.validate_password(
            attrs["password"], User(**{k: v for k, v in attrs.items() if k != "password"})
        )
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(self.context["request"], **attrs)
        if user is None:
            raise serializers.ValidationError("Invalid credentials.")
        attrs["user"] = user
        return attrs
