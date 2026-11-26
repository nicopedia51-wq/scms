from django.contrib import admin

from .models import ApprovalStep, AuditLog, Certificate, ClearanceRequest, Notification


class StepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 0


@admin.register(ClearanceRequest)
class RequestAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "reason", "academic_year", "status", "created_at")
    list_filter = ("status", "reason")
    inlines = [StepInline]


admin.site.register(Certificate)
admin.site.register(Notification)


@admin.register(AuditLog)
class AuditAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "actor", "action", "request")
