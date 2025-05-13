from django import forms #formulare
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

User = get_user_model()


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    
    role_id = forms.CharField(
        initial='viewer', #rolul este viewer by default
        widget=forms.HiddenInput()
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'role_id', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'})
        }
    
    def clean_password2(self): #validare parole
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2
    
    def save(self, commit=True): #salvare in bd
        user = super().save(commit=False)
        user.password_hash = make_password(self.cleaned_data["password1"])
        user.role_id = 'viewer'
        if commit:
            user.save()
        return user

class BaseUserForm(forms.ModelForm):
    password1 = forms.CharField(
        label='New Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    password2 = forms.CharField(
        label='Confirm New Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    team_id = forms.ChoiceField(
        label='Favorite Team',
        choices=[
            ('', 'Select a team'),
            ('mercedes', 'Mercedes'),
            ('red_bull', 'Red Bull'),
            ('ferrari', 'Ferrari'),
            ('mclaren', 'McLaren'),
            ('alpine', 'Alpine'),
            ('aston_martin', 'Aston Martin'),
            ('williams', 'Williams'),
            ('haas', 'Haas'),
            ('rb', 'RB'),
            ('sauber', 'Sauber')
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT team_id FROM user_team_access WHERE user_id = %s AND is_primary = TRUE",
                    [self.instance.user_id]
                )
                result = cursor.fetchone()
                if result:
                    self.initial['team_id'] = result[0]
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        
        if password1 or password2:
            if not password1:
                raise forms.ValidationError("New Password")
            if not password2:
                raise forms.ValidationError("Confirm the new password")
            if password1 != password2:
                raise forms.ValidationError("Passwords don't match")
        
        return password2
    
    def save(self, commit=True):
        user = super().save(commit=False)
        password1 = self.cleaned_data.get("password1")
        if password1:
            user.password_hash = make_password(password1)
        
        if commit:
            user.save()
            
            team_id = self.cleaned_data.get('team_id')
            if team_id:
                try:
                    from django.db import connection
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT access_id FROM user_team_access WHERE user_id = %s AND team_id = %s",
                            [user.user_id, team_id]
                        )
                        existing = cursor.fetchone()
                        
                        if existing:
                            cursor.execute(
                                "UPDATE user_team_access SET is_primary = TRUE WHERE access_id = %s",
                                [existing[0]]
                            )
                            cursor.execute(
                                "UPDATE user_team_access SET is_primary = FALSE WHERE user_id = %s AND access_id != %s",
                                [user.user_id, existing[0]]
                            )
                        else:
                            cursor.execute(
                                "UPDATE user_team_access SET is_primary = FALSE WHERE user_id = %s",
                                [user.user_id]
                            )
                            cursor.execute(
                                "INSERT INTO user_team_access (user_id, team_id, is_primary) VALUES (%s, %s, TRUE)",
                                [user.user_id, team_id]
                            )
                except Exception as e:
                    print(f"Error saving team relationship: {e}")
        
        return user
    
class ProfileForm(BaseUserForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'team_id']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class AdminUserForm(BaseUserForm):
    role_id = forms.ChoiceField(
        label='Role',
        choices=[
            ('viewer', 'Viewer'),
            ('team_member', 'Team Member'),
            ('analyst', 'Analyst'),
            ('admin', 'Administrator')
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role_id', 'team_id']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }