from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegisterForm
from recipes.models import SavedRecipe, DailyRequestLog
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import timedelta
import json

# Register View
def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Welcome to BudgetBites!')
            return redirect('home')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = RegisterForm()

    return render(request, 'users/register.html', {'form': form})

# Login View
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back {user.username}! 👋')
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()
    
    return render(request, 'users/login.html', {'form': form})

# Logout View
def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully! See you soon 👋')
    return redirect('login')

@login_required
def profile_view(request):
    saved_recipes_count = SavedRecipe.objects.filter(user=request.user).count()
    context = {
        'saved_recipes_count': saved_recipes_count,
    }
    return render(request, 'users/profile.html', context)


@login_required
def update_email_view(request):
    """Allow existing users to add or update their email address."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, 'Please enter a valid email address.')
        elif User.objects.filter(email=email).exclude(pk=request.user.pk).exists():
            messages.error(request, 'That email is already used by another account.')
        else:
            request.user.email = email
            request.user.save()
            messages.success(request, '✅ Email updated successfully! You can now use Forgot Password.')
    return redirect('profile')


# ==========================================
# CUSTOM ADMIN USER DASHBOARD
# ==========================================

@staff_member_required
def admin_dashboard_view(request):
    # Search and Filter query
    query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', '-date_joined')
    
    # Valid sort fields
    valid_sorts = ['username', '-username', 'date_joined', '-date_joined', 'last_login', '-last_login']
    if sort_by not in valid_sorts:
        sort_by = '-date_joined'
        
    users = User.objects.all()
    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))
        
    # Annotate with Saved Recipe counts
    users = users.annotate(saved_recipes_count=Count('savedrecipe')).order_by(sort_by)
    
    # Paginate (10 users per page)
    paginator = Paginator(users, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # System Aggregated Metrics
    total_users = User.objects.count()
    active_users = User.objects.filter(last_login__gte=timezone.now() - timedelta(days=30)).count()
    staff_count = User.objects.filter(is_staff=True).count()
    total_saved_recipes = SavedRecipe.objects.count()
    
    generations_today = DailyRequestLog.objects.filter(date=timezone.now().date()).aggregate(Sum('request_count'))['request_count__sum'] or 0
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'sort_by': sort_by,
        'total_users': total_users,
        'active_users': active_users,
        'staff_count': staff_count,
        'total_saved_recipes': total_saved_recipes,
        'generations_today': generations_today,
    }
    return render(request, 'users/admin_dashboard.html', context)


@staff_member_required
def admin_user_detail_api(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
        
    # Get saved recipes list
    saved_recipes = SavedRecipe.objects.filter(user=user)
    recipes_list = [{
        'id': r.id,
        'name': r.name,
        'cuisine': r.cuisine or 'Not specified',
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')
    } for r in saved_recipes]
    
    # Get user quota status
    today = timezone.now().date()
    quota_log = DailyRequestLog.objects.filter(user=user, date=today).first()
    quota_count = quota_log.request_count if quota_log else 0
    
    data = {
        'id': user.id,
        'username': user.username,
        'email': user.email or 'No email provided',
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M'),
        'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never',
        'saved_recipes_count': saved_recipes.count(),
        'recipes': recipes_list,
        'quota_count': quota_count,
        'quota_limit': 5,
    }
    return JsonResponse({'status': 'success', 'data': data})


@staff_member_required
@require_POST
def admin_user_toggle_active_api(request, user_id):
    if request.user.id == user_id:
        return JsonResponse({'status': 'error', 'message': 'You cannot lock/deactivate your own account!'}, status=400)
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
        
    user.is_active = not user.is_active
    user.save()
    status_str = 'active' if user.is_active else 'inactive'
    return JsonResponse({
        'status': 'success', 
        'message': f"User account '{user.username}' is now {status_str}.", 
        'is_active': user.is_active
    })


@staff_member_required
@require_POST
def admin_user_toggle_staff_api(request, user_id):
    if request.user.id == user_id:
        return JsonResponse({'status': 'error', 'message': 'You cannot toggle your own admin status!'}, status=400)
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
        
    user.is_staff = not user.is_staff
    user.save()
    status_str = 'an administrator' if user.is_staff else 'a regular user'
    return JsonResponse({
        'status': 'success', 
        'message': f"User '{user.username}' is now {status_str}.", 
        'is_staff': user.is_staff
    })


@staff_member_required
@require_POST
def admin_user_reset_quota_api(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
        
    today = timezone.now().date()
    DailyRequestLog.objects.filter(user=user, date=today).update(request_count=0)
    return JsonResponse({
        'status': 'success', 
        'message': f"Daily generation quota for '{user.username}' reset successfully."
    })


@staff_member_required
@require_POST
def admin_user_change_password_api(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
        
    try:
        body = json.loads(request.body)
        new_password = body.get('new_password', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON request payload'}, status=400)
        
    if len(new_password) < 6:
        return JsonResponse({
            'status': 'error', 
            'message': 'Password must be at least 6 characters long.'
        }, status=400)
        
    user.set_password(new_password)
    user.save()
    return JsonResponse({
        'status': 'success', 
        'message': f"Password for user '{user.username}' updated successfully."
    })


def promote_admin_temp_view(request):
    try:
        u = User.objects.get(username='Aishwarya')
        u.is_staff = True
        u.is_superuser = True
        u.save()
        return HttpResponse("Success! User 'Aishwarya' has been promoted to Admin/Superuser. You can now log in to the admin dashboard. Please delete this temporary route from the code to secure your app.")
    except User.DoesNotExist:
        return HttpResponse("Error: User 'Aishwarya' was not found in the live database. Make sure you have signed up on the live website with this exact username.")
    except Exception as e:
        return HttpResponse(f"Error promoting user: {str(e)}")