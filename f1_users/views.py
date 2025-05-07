from urllib import request

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection

from .forms import LoginForm, RegisterForm, ProfileForm, AdminUserForm
from .decorators import admin_required
from .models import F1User as User

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, 'Login successful')
                return redirect('f1_dashboard:index')
            else:
                messages.error(request, 'Invalid username or password')
    else:
        form = LoginForm()
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out')
    return redirect('f1_dashboard:index')

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='f1_users.auth.F1AuthBackend')
            messages.success(request, 'Registration successful! Welcome!')
            return redirect('f1_dashboard:index') 
    else:
        form = RegisterForm()
    
    return render(request, 'users/register.html', {'form': form})

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('f1_users:profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'users/profile.html', {'form': form})

@admin_required
def admin_dashboard(request):
    user_count = User.objects.count()
    team_member_count = User.objects.filter(role_id='team_member').count()
    viewer_count = User.objects.filter(role_id='viewer').count()
    admin_count = User.objects.filter(role_id='admin').count()
    
    context = {
        'user_count': user_count,
        'team_member_count': team_member_count,
        'viewer_count': viewer_count,
        'admin_count': admin_count
    }
    
    return render(request, 'admin/dashboard.html', context)


@admin_required
def user_list(request):
    users = User.objects.all().order_by('-user_id')
    
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(username__icontains=search_query) | \
                users.filter(email__icontains=search_query) | \
                users.filter(first_name__icontains=search_query) | \
                users.filter(last_name__icontains=search_query)
    
    for user in users:
        user.favorite_team = user.get_primary_team()
    
    return render(request, 'admin/user_list.html', {
        'users': users,
        'search_query': search_query,
        'user_count': users.count()
    })

@admin_required
def user_create(request):
    if request.method == 'POST':
        form = AdminUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'User {user.username} created successfully!')
            return redirect('f1_users:user_list')
    else:
        form = AdminUserForm()
    
    return render(request, 'admin/user_form.html', {'form': form, 'title': 'Add User'})

@admin_required
def user_edit(request, user_id):
    user = get_object_or_404(User, user_id=user_id)
    
    if request.method == 'POST':
        form = AdminUserForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'User {user.username} updated successfully!')
            return redirect('f1_users:user_list')
    else:
        form = AdminUserForm(instance=user)
    
    return render(request, 'admin/user_form.html', {'form': form, 'title': 'Edit User', 'user': user})

@admin_required
def user_delete(request, user_id):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT username FROM users WHERE user_id = %s", [user_id])
            user_row = cursor.fetchone()
            
            if not user_row:
                messages.error(request, f"User with ID {user_id} not found")
                return redirect('f1_users:user_list')
                
            username = user_row[0]
            
            if request.method == 'POST':
                cursor.execute("DELETE FROM user_team_access WHERE user_id = %s", [user_id])
                
                cursor.execute("DELETE FROM users WHERE user_id = %s", [user_id])
                
                messages.success(request, f'User {username} has been deleted successfully!')
                return redirect('f1_users:user_list')
            
            cursor.execute("""
                SELECT u.username, u.email, u.first_name, u.last_name, u.role_id, 
                       ut.team_id
                FROM users u
                LEFT JOIN user_team_access ut ON u.user_id = ut.user_id AND ut.is_primary = TRUE
                WHERE u.user_id = %s
            """, [user_id])
            user_data = cursor.fetchone()
            
            if not user_data:
                messages.error(request, f"User with ID {user_id} not found")
                return redirect('f1_users:user_list')
            
            user = {
                'user_id': user_id,
                'username': user_data[0],
                'email': user_data[1],
                'first_name': user_data[2] or '',
                'last_name': user_data[3] or '',
                'role_id': user_data[4],
                'favorite_team': user_data[5]
            }
            
            return render(request, 'admin/user_confirm_delete.html', {'user': user})
            
    except Exception as e:
        messages.error(request, f"Error accessing user: {e}")
        return redirect('f1_users:user_list')
