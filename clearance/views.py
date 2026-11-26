import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.forms import OfficerCreateForm
from accounts.models import User

from . import services
from .forms import ClearanceRequestForm, DecisionForm, ReportFilterForm, ResubmitForm
from .models import ApprovalStep, AuditLog, Certificate, ClearanceRequest
from .services import ClearanceError

STUDENT, OFFICER, ADMIN = User.Role.STUDENT, User.Role.OFFICER, User.Role.ADMIN


@login_required
def home(request):
    """Send each user to the dashboard of their role."""
    target = {STUDENT: "student_dashboard", OFFICER: "officer_dashboard", ADMIN: "manage_dashboard"}[request.user.role]
    return redirect(target)


# ------------------------------------------------------------------ student
@role_required(STUDENT)
def student_dashboard(request):
    reqs = request.user.requests.prefetch_related("steps__department")
    return render(request, "student/dashboard.html", {"requests": reqs})


@role_required(STUDENT)
def apply(request):
    form = ClearanceRequestForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            req = services.submit_request(
                request.user, form.cleaned_data["reason"], form.cleaned_data["academic_year"], form.cleaned_data.get("document")
            )
        except ClearanceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Clearance request submitted.")
            return redirect("request_detail", pk=req.pk)
    return render(request, "student/apply.html", {"form": form})


@login_required
def request_detail(request, pk):
    req = get_object_or_404(ClearanceRequest.objects.prefetch_related("steps__department", "steps__officer"), pk=pk)
    if not (req.student_id == request.user.id or request.user.role == ADMIN):
        raise PermissionDenied
    form = ResubmitForm()
    return render(request, "student/request_detail.html", {"req": req, "form": form})


@role_required(STUDENT)
@require_POST
def resubmit(request, pk):
    req = get_object_or_404(ClearanceRequest, pk=pk, student=request.user)
    form = ResubmitForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            services.resubmit(request.user, req, form.cleaned_data.get("document"))
            messages.success(request, "Request resubmitted to the office that rejected it.")
        except ClearanceError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("request_detail", pk=pk)


@login_required
def document_download(request, pk):
    """Uploaded documents are only served to people allowed to see the request."""
    req = get_object_or_404(ClearanceRequest, pk=pk)
    if not services.can_view_request(request.user, req):
        raise PermissionDenied
    if not req.document:
        raise Http404("No document uploaded.")
    return FileResponse(req.document.open("rb"), as_attachment=True, filename=req.document.name.split("/")[-1])


@login_required
def certificate(request, pk):
    req = get_object_or_404(ClearanceRequest, pk=pk, status=ClearanceRequest.Status.APPROVED)
    if not (req.student_id == request.user.id or request.user.role == ADMIN):
        raise PermissionDenied
    cert = req.certificate
    ctx = {
        "req": req, "cert": cert,
        "verify_url": request.build_absolute_uri(reverse("verify", args=[cert.code])),
    }
    html = render_to_string("certificate.html", ctx, request=request)
    if request.GET.get("format") != "html":
        pdf = services.render_pdf(html, base_url=request.build_absolute_uri("/"))
        if pdf:
            resp = HttpResponse(pdf, content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="clearance-{cert.code}.pdf"'
            return resp
    return HttpResponse(html)  # printable page: use the browser's Print > Save as PDF


def verify(request, code=None):
    """Public page: anyone can check a certificate code is genuine."""
    code = (code or request.GET.get("code", "")).strip().upper()
    cert = Certificate.objects.select_related("request__student__school").filter(code=code).first() if code else None
    return render(request, "verify.html", {"code": code, "cert": cert})


# ------------------------------------------------------------------ officer
@role_required(OFFICER)
def officer_dashboard(request):
    return render(request, "officer/dashboard.html", {"steps": services.actionable_steps_for(request.user)})


@role_required(OFFICER)
def officer_history(request):
    qs = ApprovalStep.objects.filter(department=request.user.department).exclude(status=ApprovalStep.Status.PENDING)
    qs = qs.select_related("request__student__school", "officer").order_by("-acted_at")
    if request.user.department and request.user.department.is_school_office:
        qs = qs.filter(request__student__school=request.user.school)
    return render(request, "officer/history.html", {"steps": qs[:200]})


@role_required(OFFICER)
def officer_review(request, step_id):
    step = get_object_or_404(ApprovalStep.objects.select_related("request__student__school", "department"), pk=step_id)
    if not services.can_view_request(request.user, step.request):
        raise PermissionDenied
    can_act = services.can_act(request.user, step)
    form = DecisionForm(request.POST or None)
    if request.method == "POST":
        if not can_act:
            raise PermissionDenied
        if form.is_valid():
            try:
                services.decide(request.user, step, form.cleaned_data["decision"] == "approve", form.cleaned_data["comment"])
            except ClearanceError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Decision recorded.")
                return redirect("officer_dashboard")
    return render(request, "officer/review.html", {"step": step, "req": step.request, "form": form, "can_act": can_act})


# ------------------------------------------------------------------ administrator
@role_required(ADMIN)
def manage_dashboard(request):
    report = services.build_report()
    recent = ClearanceRequest.objects.select_related("student")[:8]
    return render(request, "manage/dashboard.html", {"report": report, "recent": recent})


def _report_from_request(request):
    form = ReportFilterForm(request.GET or None)
    data = form.cleaned_data if form.is_valid() else {}
    return form, services.build_report(data.get("school"), data.get("department"), data.get("date_from"), data.get("date_to"))


@role_required(ADMIN)
def manage_reports(request):
    form, report = _report_from_request(request)
    return render(request, "manage/reports.html", {"form": form, "report": report, "query": request.GET.urlencode()})


@role_required(ADMIN)
def manage_reports_csv(request):
    _, report = _report_from_request(request)
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="clearance-report.csv"'
    w = csv.writer(resp)
    w.writerow(["ID", "Registration no.", "Student", "School", "Reason", "Year", "Status", "Waiting at", "Hours waiting", "Submitted"])
    for row in report["rows"]:
        r = row["request"]
        w.writerow([r.pk, r.student.username, r.student.display_name, r.student.school, r.get_reason_display(),
                    r.academic_year, r.get_status_display(), row["waiting_at"] or "", row["waiting_hours"] or "",
                    r.created_at.strftime("%Y-%m-%d %H:%M")])
    return resp


@role_required(ADMIN)
def manage_officers(request):
    form = OfficerCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Officer {user.username} created.")
        return redirect("manage_officers")
    officers = User.objects.filter(role=OFFICER).select_related("department", "school").order_by("department__order", "username")
    return render(request, "manage/officers.html", {"form": form, "officers": officers})


@role_required(ADMIN)
def manage_audit(request):
    return render(request, "manage/audit.html", {"logs": AuditLog.objects.select_related("actor", "request")[:200]})


# ------------------------------------------------------------------ notifications
@login_required
def notification_list(request):
    items = list(request.user.notifications.select_related("request")[:100])
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, "notifications.html", {"items": items})
