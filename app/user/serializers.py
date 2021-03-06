from django.contrib.auth import get_user_model, authenticate
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the users object"""
    image = serializers.CharField(required=False)

    class Meta:
        model = get_user_model()
        fields = ("email", "password", "name", "image")
        extra_kwargs = {
            "password": {
                "write_only": True,
                "min_length": 12
            }
        }

    def create(self, validated_data: dict):
        """Create a new user with encrypted password and return it"""
        return get_user_model().objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        """Update a user, setting the password correctly and return it"""
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)

        if password:
            user.set_password(password)
            user.save()

        return user


class AuthTokenSerializer(serializers.Serializer):
    """Serializer for the API user authentication object"""
    email = serializers.CharField()
    password = serializers.CharField(
        style={"input_type": "password"},
        trim_whitespace=False,
        min_length=12
    )

    def validate(self, attrs):
        """Validate and authenticate the API user"""
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password
        )

        if not user:
            msg = _("Unable to authenticate with provided credentials")
            raise serializers.ValidationError(msg, code="authentication")

        attrs["user"] = user
        return attrs


class UserImageSerializer(serializers.ModelSerializer):
    """Serializer for uploading user image"""

    class Meta:
        model = get_user_model()
        fields = ("id", "image",)
        read_only_fields = ("id",)
