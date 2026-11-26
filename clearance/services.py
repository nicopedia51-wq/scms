"""Business rules of the clearance workflow. Views stay thin; all rules live here (easy to unit-test)."""
import uuid
from collections import defaultdict

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from accounts.models import Department, User

from .models import ApprovalStep, AuditLog, Certificate, ClearanceRequest, Notification


class ClearanceError(Exception):
    """Raised when an action breaks a clearance rule; the message is shown to the user."""


# ---------------------------------------------------------------- helpers
def log(actor, action, req=None, details=""):
    AuditLog.objects.create(actor=actor, action=action, request=req, details=details)


def notify(user, message, req=None):
    """In-app notification plus an email (the in-app inbox is the fallback if email is delayed)."""
    Notification.objects.create(user=user, message=message[:255], request=req)
    if user.email:
        send_mail("Student Clearance System", message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)


def officers_for_step(step):
    officers = User.objects.filter(role=User.Role.OFFICER, department=step.department, is_active=True)
    if step.department.is_school_office:
        officers = officers.filter(school=step.request.student.school)
    return officers


def _notify_officers(step):
    for officer in officers_for_step(step):
        notify(officer, f"New clearance request from {step.request.student.display_name} awaits your decision.", step.request)


# ---------------------------------------------------------------- permissions
def _officer_covers(officer, step):
    """Right department and (for a school office) the right school."""
    if officer.role != User.Role.OFFICER or officer.department_id != step.department_id:
        return False
    if step.department.is_school_office:
        return officer.school_id == step.request.student.school_id
    return True


def can_act(officer, step):
    """An officer may decide only on the CURRENT pending step of an open request."""
    req = step.request
    return (
        _officer_covers(officer, step)
        and step.status == ApprovalStep.Status.PENDING
        and req.status in (ClearanceRequest.Status.SUBMITTED, ClearanceRequest.Status.IN_PROGRESS)
        and req.current_step == step
    )


def can_view_request(user, req):
    if user.role == User.Role.ADMIN:
        return True
    if user.role == User.Role.STUDENT:
        return req.student_id == user.id
    if user.role == User.Role.OFFICER:
        step = req.steps.filter(department_id=user.department_id).select_related("department", "request__student").first()
        return bool(step and _officer_covers(user, step))
    return False


def actionable_steps_for(officer):
    """Steps this officer can decide right now."""
    if officer.role != User.Role.OFFICER or not officer.department_id:
        return []
    qs = ApprovalStep.objects.filter(
        department=officer.department,
        status=ApprovalStep.Status.PENDING,
        request__status__in=[ClearanceRequest.Status.SUBMITTED, ClearanceRequest.Status.IN_PROGRESS],
    ).select_related("request__student__school", "department").order_by("activated_at")
    return [s for s in qs if can_act(officer, s)]


# ---------------------------------------------------------------- workflow
@transaction.atomic
def submit_request(student, reason, academic_year, document=None):
    if student.role != User.Role.STUDENT:
        raise ClearanceError("Only students can apply for clearance.")
    if student.requests.filter(status__in=[
        ClearanceRequest.Status.SUBMITTED, ClearanceRequest.Status.IN_PROGRESS, ClearanceRequest.Status.REJECTED,
    ]).exists():
        raise ClearanceError("You already have an open clearance request. Finish or resubmit it first.")
    if student.requests.filter(status=ClearanceRequest.Status.APPROVED, academic_year=academic_year).exists():
        raise ClearanceError("You have already been cleared for that academic year.")
    departments = list(Department.objects.order_by("order"))
    if not departments:
        raise ClearanceError("No clearance offices are configured yet. Contact the administrator.")
    if not student.school_id:
        raise ClearanceError("Your profile has no school. Contact the administrator.")

    req = ClearanceRequest.objects.create(
        student=student, reason=reason, academic_year=academic_year, document=document or ""
    )
    steps = [ApprovalStep.objects.create(request=req, department=d) for d in departments]
    steps[0].activated_at = timezone.now()
    steps[0].save(update_fields=["activated_at"])

    log(student, "Request submitted", req, f"Reason: {req.get_reason_display()}, year {academic_year}")
    notify(student, f"Your clearance request #{req.pk} was submitted. First office: {steps[0].department.name}.", req)
    _notify_officers(steps[0])
    return req


@transaction.atomic
def decide(officer, step, approve, comment=""):
    step = ApprovalStep.objects.select_for_update(of=("self",)).select_related("request__student", "department").get(pk=step.pk)
    if not can_act(officer, step):
        raise ClearanceError("You cannot act on this request right now (wrong office, not its turn, or already decided).")
    comment = (comment or "").strip()
    if not approve and not comment:
        raise ClearanceError("Give a reason when rejecting a request, so the student knows what to fix.")

    req = step.request
    now = timezone.now()
    step.officer, step.comment, step.acted_at = officer, comment, now

    if not approve:
        step.status = ApprovalStep.Status.REJECTED
        step.save()
        req.status = ClearanceRequest.Status.REJECTED
        req.save()
        log(officer, f"Rejected by {step.department.name}", req, comment)
        notify(req.student, f"{step.department.name} rejected your clearance: {comment}", req)
        return req

    step.status = ApprovalStep.Status.APPROVED
    step.save()
    log(officer, f"Approved by {step.department.name}", req, comment)
    nxt = req.current_step
    if nxt is None:
        req.status = ClearanceRequest.Status.APPROVED
        req.completed_at = now
        req.save()
        issue_certificate(req)
        notify(req.student, "All offices have cleared you. Your clearance certificate is ready to download.", req)
    else:
        req.status = ClearanceRequest.Status.IN_PROGRESS
        req.save()
        nxt.activated_at = now
        nxt.save(update_fields=["activated_at"])
        notify(req.student, f"{step.department.name} approved. Next office: {nxt.department.name}.", req)
        _notify_officers(nxt)
    return req


@transaction.atomic
def resubmit(student, req, document=None):
    """After a rejection the student fixes the problem and the SAME office decides again."""
    if req.student_id != student.id or req.status != ClearanceRequest.Status.REJECTED:
        raise ClearanceError("Only your own rejected requests can be resubmitted.")
    step = req.steps.filter(status=ApprovalStep.Status.REJECTED).first()
    previous = step.comment
    step.status = ApprovalStep.Status.PENDING
    step.officer, step.acted_at, step.comment = None, None, ""
    step.activated_at = timezone.now()
    step.save()
    if document:
        req.document = document
    req.status = ClearanceRequest.Status.IN_PROGRESS
    req.save()
    log(student, "Request resubmitted", req, f"Previous rejection: {previous}")
    notify(student, f"Request #{req.pk} resubmitted to {step.department.name}.", req)
    _notify_officers(step)
    return req


def _new_code():
    while True:
        code = "SCMS-" + uuid.uuid4().hex[:10].upper()
        if not Certificate.objects.filter(code=code).exists():
            return code


def issue_certificate(req):
    """Eligibility rule: a certificate exists only when EVERY step is approved."""
    if req.steps.exclude(status=ApprovalStep.Status.APPROVED).exists() or not req.steps.exists():
        raise ClearanceError("A certificate can only be issued after every office has approved.")
    cert, created = Certificate.objects.get_or_create(request=req, defaults={"code": _new_code()})
    if created:
        log(None, "Certificate issued", req, cert.code)
    return cert


def render_pdf(html, base_url=None):
    """Return PDF bytes via WeasyPrint, or None when it is not installed/usable (e.g. missing GTK on Windows)."""
    try:
        from weasyprint import HTML
        return HTML(string=html, base_url=base_url).write_pdf()
    except Exception:
        return None


# ---------------------------------------------------------------- reporting
def build_report(school=None, department=None, date_from=None, date_to=None):
    """Counts, per-office delay statistics and the list of requests for the admin reports page."""
    qs = ClearanceRequest.objects.select_related("student__school").prefetch_related("steps__department")
    if school:
        qs = qs.filter(student__school=school)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    requests_list = list(qs)

    now = timezone.now()
    rows = []
    for r in requests_list:
        cur = r.current_step
        if department and not (cur and cur.department_id == department.id and r.status != ClearanceRequest.Status.APPROVED):
            continue
        waiting = None
        if cur and cur.activated_at and r.status in (ClearanceRequest.Status.SUBMITTED, ClearanceRequest.Status.IN_PROGRESS):
            waiting = round((now - cur.activated_at).total_seconds() / 3600, 1)
        rows.append({"request": r, "waiting_at": cur.department if cur and r.status != ClearanceRequest.Status.APPROVED else None, "waiting_hours": waiting})

    counts = {"waiting": 0, "in_progress": 0, "approved": 0, "rejected": 0}
    for row in rows:
        st = row["request"].status
        counts["waiting" if st == "submitted" else st] += 1

    per_dept = defaultdict(lambda: {"pending": 0, "overdue": 0, "hours": []})
    for row in rows:
        for step in row["request"].steps.all():
            d = per_dept[step.department]
            if step.acted_at and step.activated_at and step.status != ApprovalStep.Status.PENDING:
                d["hours"].append((step.acted_at - step.activated_at).total_seconds() / 3600)
        cur = row["request"].current_step
        if cur and row["waiting_hours"] is not None and cur.status == ApprovalStep.Status.PENDING:
            per_dept[cur.department]["pending"] += 1
            if row["waiting_hours"] > settings.CLEARANCE_SLA_HOURS:
                per_dept[cur.department]["overdue"] += 1
    dept_stats = []
    for d in Department.objects.order_by("order"):
        s = per_dept.get(d, {"pending": 0, "overdue": 0, "hours": []})
        avg = round(sum(s["hours"]) / len(s["hours"]), 1) if s["hours"] else None
        dept_stats.append({"department": d, "pending": s["pending"], "overdue": s["overdue"], "avg_hours": avg})
    return {"rows": rows, "counts": counts, "dept_stats": dept_stats, "total": len(rows)}
