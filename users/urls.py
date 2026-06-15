from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/update-email/', views.update_email_view, name='update_email'),

    # ── Forgot Password Flow (Django Built-in) ──────────────────────────────
    path('forgot-password/',
         auth_views.PasswordResetView.as_view(
             template_name='users/forgot_password.html',
             email_template_name='users/password_reset_email.html',
             subject_template_name='users/password_reset_subject.txt',
             success_url='/forgot-password/sent/',
         ),
         name='password_reset'),

    path('forgot-password/sent/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_sent.html',
         ),
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html',
             success_url='/reset/complete/',
         ),
         name='password_reset_confirm'),

    path('reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html',
         ),
         name='password_reset_complete'),
    # ────────────────────────────────────────────────────────────────────────

    # Custom Admin Dashboard
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-dashboard/api/user/<int:user_id>/detail/', views.admin_user_detail_api, name='admin_user_detail_api'),
    path('admin-dashboard/api/user/<int:user_id>/toggle-active/', views.admin_user_toggle_active_api, name='admin_user_toggle_active_api'),
    path('admin-dashboard/api/user/<int:user_id>/toggle-staff/', views.admin_user_toggle_staff_api, name='admin_user_toggle_staff_api'),
    path('admin-dashboard/api/user/<int:user_id>/reset-quota/', views.admin_user_reset_quota_api, name='admin_user_reset_quota_api'),
    path('admin-dashboard/api/user/<int:user_id>/change-password/', views.admin_user_change_password_api, name='admin_user_change_password_api'),

    # Temporary admin promotion (free tier fallback)
    path('promote-admin-temp-key-123/', views.promote_admin_temp_view, name='promote_admin_temp'),
]