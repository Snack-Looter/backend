from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, user_name, name, phone_number, password=None, koperasi_id=None, gender=""):
        if not email:
            raise ValueError("Email wajib diisi")
        user = self.model(
            email=self.normalize_email(email),
            user_name=user_name,
            name=name,
            phone_number=phone_number,
            koperasi_id=koperasi_id,
            gender=gender,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, user_name, name, phone_number, password=None):
        # Superuser sistem tidak terikat koperasi manapun (koperasi=None).
        user = self.create_user(email, user_name, name, phone_number, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """
    Tabel dasar akun. Mewarisi AbstractBaseUser agar terintegrasi dengan
    Django auth + Simple JWT. password_hash dikelola otomatis oleh
    AbstractBaseUser.password (sudah di-hash, jangan tambah kolom lain).
    """
    GENDER_MALE = "male"
    GENDER_FEMALE = "female"
    GENDER_CHOICES = [
        (GENDER_MALE, "Laki-laki"),
        (GENDER_FEMALE, "Perempuan"),
    ]

    user_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    user_name = models.CharField(max_length=50, unique=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(max_length=255, unique=True)
    profile_picture = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # True = petugas koperasi

    # Permanen sejak registrasi (One Account, One Cooperative). Nullable karena
    # superuser sistem tidak terikat koperasi manapun; petugas/kasir WAJIB
    # punya ini supaya transaksi POS bisa divalidasi ke koperasi yang benar.
    koperasi = models.ForeignKey(
        "Koperasi", on_delete=models.RESTRICT, related_name="users", null=True, blank=True,
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["user_name", "name", "phone_number"]

    class Meta:
        db_table = 'kopquest"."user'

    def __str__(self):
        return self.user_name


class Province(models.Model):
    province_id = models.AutoField(primary_key=True)
    province_name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'kopquest"."province'

    def __str__(self):
        return self.province_name


class City(models.Model):
    city_id = models.AutoField(primary_key=True)
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name="cities")
    city_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'kopquest"."city'
        constraints = [
            models.UniqueConstraint(fields=["province", "city_name"], name="uq_city_province_name"),
        ]

    def __str__(self):
        return self.city_name


class Koperasi(models.Model):
    koperasi_id = models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="koperasi_list")
    koperasi_name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'kopquest"."koperasi'

    def __str__(self):
        return self.koperasi_name


class Player(models.Model):
    """Ekstensi User untuk fitur gamifikasi (1:1 dengan User)."""
    user = models.OneToOneField(
        User, primary_key=True, db_column="user_id",
        on_delete=models.CASCADE, related_name="player",
    )
    total_xp = models.PositiveIntegerField(default=0)
    referred_by = models.ForeignKey(
        User, null=True, blank=True, db_column="referred_by_user_id",
        on_delete=models.SET_NULL, related_name="referrals",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kopquest"."player'

    def __str__(self):
        return f"Player({self.user.user_name})"


class Role(models.Model):
    role_id = models.AutoField(primary_key=True)
    role_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'kopquest"."role'

    def __str__(self):
        return self.role_name


class PlayerRole(models.Model):
    """Junction N:M Player<->Role. Level/XP/reward independen per role."""
    player_role_id = models.BigAutoField(primary_key=True)
    player = models.ForeignKey(
        Player, db_column="user_id", on_delete=models.CASCADE, related_name="player_roles",
    )
    role = models.ForeignKey(Role, on_delete=models.RESTRICT, related_name="player_roles")
    current_level_number = models.PositiveIntegerField(default=1)
    role_xp = models.PositiveIntegerField(default=0)
    mission_completed_count = models.PositiveIntegerField(default=0)
    mission_failed_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kopquest"."player_role'
        constraints = [
            models.UniqueConstraint(fields=["player", "role"], name="uq_player_role"),
        ]

    def __str__(self):
        return f"{self.player.user.user_name} - {self.role.role_name} (Lv{self.current_level_number})"
