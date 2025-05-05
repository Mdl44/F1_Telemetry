from django.http import HttpResponseForbidden
from functools import wraps

def team_member_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_team_member():
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("You are not allowed to access this page.")
    return _wrapped_view

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_admin_user():
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("You are not allowed to access this page.")
    return _wrapped_view