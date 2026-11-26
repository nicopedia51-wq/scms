from django.contrib.auth.models import AbstractUser
from django.db import models


class School(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(models.Model):
    """A clearance office (Library, Finance, ...). `order` fixes the approval sequence."""

    name = models.CharField(max_length=120, unique=True)
    order = models.PositiveSmallIntegerField(unique=True, help_text="Position in the clearance sequence (1 = first).")
    is_school_office = models.BooleanField(
        default=False,
        help_text="If ticked, only an officer from the student's own school can act on this step.",
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """One user model for all three roles. Students use their registration number as username."""

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        OFFICER = "officer", "Clearance officer"
        ADMIN = "admin", "Administrator"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    school = models.ForeignKey(School, null=True, blank=True, on_delete=models.SET_NULL, related_name="users")
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="officers"
    )

    def save(self, *args, **kwargs):
        if self.role == self.Role.ADMIN:
            self.is_staff = True  # lets administrators open the Django admin site
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return f"{self.display_name} ({self.get_role_display()})"
