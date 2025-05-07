from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import make_password
from django.db import connection


class F1UserManager(BaseUserManager):
    def get_by_natural_key(self, username):
        return self.get(username=username)
        
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Utilizatorul trebuie să aibă o adresă de email')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('role_id', 'admin')
        return self.create_user(username, email, password, **extra_fields)



class F1User(AbstractBaseUser):
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=100, unique=True)
    password_hash = models.CharField(max_length=255, db_column='password_hash')
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)

    role_id = models.CharField(max_length=20, default='viewer')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = F1UserManager()
    
    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['email']
    class Meta:
        db_table = 'users'
        managed = False

    def __str__(self):
        return self.username

    @property
    def password(self):
        return self.password_hash

    @password.setter
    def password(self, value):
        self.password_hash = make_password(value)

    def is_team_member(self):
        return self.role_id in ['team_member', 'analyst', 'admin']

    def is_analyst(self):
        return self.role_id in ['analyst', 'admin']

    def is_admin_user(self):
        return self.role_id == 'admin'

    @property
    def is_staff(self):
        return self.role_id in ['analyst', 'admin']

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @property
    def is_superuser(self):
        return self.role_id == 'admin'

    def has_perm(self, perm, obj=None):
        if self.is_admin_user():
            return True
        elif self.is_staff and perm in ['view', 'add', 'change']:
            return True
        elif self.role_id == 'team_member' and perm == 'view':
            return True
        return False

    def has_module_perms(self, app_label):
        if self.is_admin_user():
            return True

        allowed_apps = {
            'viewer': ['f1_dashboard'],
            'team_member': ['f1_dashboard', 'f1_analysis'],
            'analyst': ['f1_dashboard', 'f1_analysis', 'f1_users'],
        }

        return app_label in allowed_apps.get(self.role_id, [])

    def can_access(self, feature):
        permission_map = {
            'view_telemetry': ['viewer', 'team_member', 'analyst', 'admin'],
            'use_ai': ['team_member', 'analyst', 'admin'],
            'create_analysis': ['analyst', 'admin'],
            'edit_users': ['admin'],
        }

        return self.role_id in permission_map.get(feature, [])
    
    def get_primary_team(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT team_id FROM user_team_access WHERE user_id = %s AND is_primary = TRUE",
                [self.user_id]
            )
            result = cursor.fetchone()
            return result[0] if result else None