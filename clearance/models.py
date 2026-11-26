from django.conf import settings
from django.db import models

from accounts.models import Department


class ClearanceRequest(models.Model):
    """One student's clearance application. Its state is acted on by officers via ApprovalSteps."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        IN_PROGRESS = "in_progress", "In progress"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class Reason(models.TextChoices):
        GRADUATION = "graduation", "Graduation"
        END_OF_YEAR = "end_of_year", "End of academic year"
        WITHDRAWAL = "withdrawal", "Withdrawal / discontinuation"
        TRANSFER = "transfer", "Transfer"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="requests")
    reason = models.CharField(max_length=20, choices=Reason.choices, default=Reason.GRADUATION)
    academic_year = models.CharField(max_length=9, help_text="e.g. 2025/2026")
    document = models.FileField(upload_to="clearance_docs/%Y/", blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Clearance #{self.pk} - {self.student.username}"

    @property
    def current_step(self):
        """The first step that is not yet approved (None when everything is approved)."""
        for step in self.steps.all():
            if step.status != ApprovalStep.Status.APPROVED:
                return step
        return None

    @property
    def progress_percent(self):
        steps = list(self.steps.all())
        if not steps:
            return 0
        done = sum(1 for s in steps if s.status == ApprovalStep.Status.APPROVED)
        return int(done * 100 / len(steps))

    @property
    def is_active(self):
        return self.status in (self.Status.SUBMITTED, self.Status.IN_PROGRESS, self.Status.REJECTED)

    @property
    def badge(self):
        return {"submitted": "secondary", "in_progress": "primary", "approved": "success", "rejected": "danger"}[self.status]


class ApprovalStep(models.Model):
    """The decision one department must make on a request, in department order."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    request = models.ForeignKey(ClearanceRequest, on_delete=models.CASCADE, related_name="steps")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="steps")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    officer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="decisions"
    )
    comment = models.TextField(blank=True)
    activated_at = models.DateTimeField(null=True, blank=True, help_text="When this step became the current one.")
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["department__order"]
        unique_together = ("request", "department")

    def __str__(self):
        return f"{self.request} / {self.department}"

    @property
    def badge(self):
        return {"pending": "secondary", "approved": "success", "rejected": "danger"}[self.status]


class Certificate(models.Model):
    request = models.OneToOneField(ClearanceRequest, on_delete=models.CASCADE, related_name="certificate")
    code = models.CharField(max_length=20, unique=True, editable=False)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    request = models.ForeignKey(ClearanceRequest, null=True, blank=True, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AuditLog(models.Model):
    """Who did what and when - kept for accountability."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    request = models.ForeignKey(ClearanceRequest, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
