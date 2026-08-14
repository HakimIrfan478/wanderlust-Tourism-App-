from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "home_country",
            "travel_preferences",
        )

    def validate_password(self, value):
        # Run Django's configured validators (length, common passwords,
        # all-numeric) so the API enforces the same policy as the admin.
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("That email address is already in use.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    favorites = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    favorite_count = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "bio",
            "home_country",
            "travel_preferences",
            "favorites",
            "favorite_count",
            "review_count",
            "date_joined",
        )
        read_only_fields = ("id", "username", "date_joined")

    def get_favorite_count(self, obj):
        return obj.favorites.count()

    def get_review_count(self, obj):
        return obj.reviews.count()

    def validate_email(self, value):
        if value and (
            User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists()
        ):
            raise serializers.ValidationError("That email address is already in use.")
        return value
