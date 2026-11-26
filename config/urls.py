from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    # Password reset (emails print to the terminal while EMAIL_BACKEND is the console backend)
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/simple_form.html",
        extra_context={"title": "Reset your password", "button": "Send reset link"}),
        name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/simple_message.html",
        extra_context={"title": "Check your email",
                       "message": "If an account exists for that email, a reset link has been sent."}),
        name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/simple_form.html",
        extra_context={"title": "Choose a new password", "button": "Save new password"}),
        name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/simple_message.html",
        extra_context={"title": "Password changed", "message": "You can now log in with your new password."}),
        name="password_reset_complete"),
    path("", include("clearance.urls")),
]
