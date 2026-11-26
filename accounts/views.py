from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import StudentRegistrationForm


def register(request):
    """Students create their own account; officers and admins are created by an administrator."""
    if request.user.is_authenticated:
        return redirect("home")
    form = StudentRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your account has been created.")
        return redirect("home")
    return render(request, "registration/register.html", {"form": form})
