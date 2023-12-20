from django.db import transaction, IntegrityError
from rest_framework import serializers, status
from rest_framework.response import Response

from accounts.models import User, StaffAuth, Profile, Todo


# Accounts --------------------------------------------------------------------------
class StaffAuthInUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffAuth
        fields = ('pk', 'user', 'company', 'is_staff', 'is_project_staff',
                  'allowed_projects', 'assigned_project', 'contract', 'payment',
                  'notice', 'project_cash', 'project_docs', 'project', 'company_cash',
                  'company_docs', 'human_resource', 'company_settings', 'auth_manage')

    @transaction.atomic
    def create(self, validated_data):
        # 1. 권한정보 테이블 입력
        many_to_many = {'allowed_projects': validated_data.pop('allowed_projects')}
        instance = StaffAuth.objects.create(**validated_data)

        # Save many-to-many relationships after the instance is created.
        for field_name, value in many_to_many.items():
            field = getattr(instance, field_name)
            field.set(value)

        # 2. 프로필 정보가 있는지 확인 후 없으면 기본 프로필 생성
        try:
            Profile.objects.get(user=validated_data['user'])
        except Profile.DoesNotExist:
            empty_profile = Profile(user=instance.user)
            empty_profile.save()

        return instance


class ProfileInUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('pk', 'name', 'birth_date', 'cell_phone')


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        help_text='변경할 필요가 없으면 비워 두십시오.',
        style={'input_type': 'password', 'placeholder': '비밀번호'}
    )
    staffauth = StaffAuthInUserSerializer(read_only=True)
    profile = ProfileInUserSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('pk', 'email', 'username', 'is_active', 'is_superuser',
                  'date_joined', 'password', 'staffauth', 'profile', 'last_login')
        read_only_fields = ('date_joined', 'last_login')

    def save(self):
        instance = User(email=self.validated_data['email'],
                        username=self.validated_data['username'])
        password = self.validated_data['password']
        instance.set_password(password)
        instance.save()
        self.instance = instance
        return self.instance


class ProfileSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True, allow_empty_file=False, required=False)

    class Meta:
        model = Profile
        fields = ('pk', 'user', 'name', 'birth_date',
                  'cell_phone', 'image', 'like_posts', 'like_comments')

    @transaction.atomic
    def update(self, instance, validated_data):
        instance.__dict__.update(**validated_data)
        instance.save()

        user = instance.user
        email = user.email
        new_email = self.initial_data.get('email')
        if email != new_email:
            if User.objects.filter(email=new_email).exists():
                raise serializers.ValidationError({'email': '이미 등록된 이메일입니다.'})
            user.email = new_email
            user.save()

        return instance


class TodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Todo
        fields = ('pk', 'user', 'title', 'completed', 'soft_deleted')

# class ChangePasswordSerializer(serializers.ModelSerializer):
#     old_password = serializers.CharField(max_length=128, write_only=True, required=True)
#     new_password = serializers.CharField(max_length=128, write_only=True, required=True)
#     confirm_password = serializers.CharField(max_length=128, write_only=True, required=True)
#
#     class Meta:
#         model = User
#         fields = ('pk', 'username', 'password', 'old_password', 'new_password', 'confirm_password')
#         extra_kwargs = {
#             "password": {"write_only": True},
#         }
#
#     def update(self, instance, validated_data):
#         instance.password = validated_data.get('password', instance.password)
#
#         old_password = self.initial_data.get('old_password')
#         new_password = self.initial_data.get('new_password')
#         confirm_password = self.initial_data.get('confirm_password')
#
#         # if not old_password:
#         #     raise serializers.ValidationError({'old_password': 'not found'})
#         #
#         # if not new_password:
#         #     raise serializers.ValidationError({'new_password': 'not found'})
#
#         # if not instance.check_password(old_password):
#         #     raise serializers.ValidationError({'old_password': 'wrong password'})
#         #
#         # if new_password != confirm_password:
#         #     raise serializers.ValidationError({'passwords': 'passwords do not match'})
#
#         if new_password == confirm_password:
#             # instance.password = new_password
#             print(instance.password)
#             instance.set_password(new_password)
#             print(instance.password)
#             instance.save()
#             return instance
#         return instance
