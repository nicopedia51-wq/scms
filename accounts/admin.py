from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Department, School, User


@admin.register(User)
class SCMSUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "school", "department", "is_active")
    list_filter = ("role", "school", "department", "is_active")
    fieldsets = UserAdmin.fieldsets + (("Clearance", {"fields": ("role", "school", "department")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Clearance", {"fields": ("role", "school", "department")}),)


admin.site.register(School)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "is_school_office")
    ordering = ("order",)
