from django.test import TestCase
from django.urls import reverse

from accounts.models import Department, School, User

from . import services
from .models import ApprovalStep, Certificate, ClearanceRequest
from .services import ClearanceError


class WorkflowTests(TestCase):
    def setUp(self):
        self.cs = School.objects.create(name="Computing")
        self.biz = School.objects.create(name="Business")
        self.lib = Department.objects.create(name="Library", order=1)
        self.fin = Department.objects.create(name="Finance", order=2)
        self.sch = Department.objects.create(name="School", order=3, is_school_office=True)
        self.student = User.objects.create_user("S1", password="pw", role="student", school=self.cs, email="s@x.com")
        self.lib_o = User.objects.create_user("lib", password="pw", role="officer", department=self.lib)
        self.fin_o = User.objects.create_user("fin", password="pw", role="officer", department=self.fin)
        self.cs_o = User.objects.create_user("cs", password="pw", role="officer", department=self.sch, school=self.cs)
        self.biz_o = User.objects.create_user("biz", password="pw", role="officer", department=self.sch, school=self.biz)
        self.admin = User.objects.create_user("adm", password="pw", role="admin")

    def _submit(self):
        return services.submit_request(self.student, "graduation", "2025/2026")

    def _step(self, req, dept):
        return req.steps.get(department=dept)

    def test_submit_creates_ordered_steps_and_only_first_is_actionable(self):
        req = self._submit()
        self.assertEqual([s.department.name for s in req.steps.all()], ["Library", "Finance", "School"])
        self.assertTrue(services.can_act(self.lib_o, self._step(req, self.lib)))
        self.assertFalse(services.can_act(self.fin_o, self._step(req, self.fin)))

    def test_cannot_skip_ahead(self):
        req = self._submit()
        with self.assertRaises(ClearanceError):
            services.decide(self.fin_o, self._step(req, self.fin), True)

    def test_full_approval_issues_certificate(self):
        req = self._submit()
        services.decide(self.lib_o, self._step(req, self.lib), True)
        services.decide(self.fin_o, self._step(req, self.fin), True)
        services.decide(self.cs_o, self._step(req, self.sch), True)
        req.refresh_from_db()
        self.assertEqual(req.status, ClearanceRequest.Status.APPROVED)
        self.assertTrue(Certificate.objects.filter(request=req).exists())

    def test_certificate_not_issued_before_all_approved(self):
        req = self._submit()
        services.decide(self.lib_o, self._step(req, self.lib), True)
        with self.assertRaises(ClearanceError):
            services.issue_certificate(req)

    def test_rejection_needs_reason_then_resubmit_returns_to_same_office(self):
        req = self._submit()
        step = self._step(req, self.lib)
        with self.assertRaises(ClearanceError):
            services.decide(self.lib_o, step, False, "  ")
        services.decide(self.lib_o, step, False, "Unreturned book")
        req.refresh_from_db()
        self.assertEqual(req.status, ClearanceRequest.Status.REJECTED)
        services.resubmit(self.student, req)
        req.refresh_from_db()
        step.refresh_from_db()
        self.assertEqual(req.status, ClearanceRequest.Status.IN_PROGRESS)
        self.assertEqual(step.status, ApprovalStep.Status.PENDING)
        self.assertTrue(services.can_act(self.lib_o, step))

    def test_school_officer_of_other_school_cannot_act(self):
        req = self._submit()
        services.decide(self.lib_o, self._step(req, self.lib), True)
        services.decide(self.fin_o, self._step(req, self.fin), True)
        step = self._step(req, self.sch)
        self.assertFalse(services.can_act(self.biz_o, step))
        self.assertTrue(services.can_act(self.cs_o, step))

    def test_one_open_request_at_a_time(self):
        self._submit()
        with self.assertRaises(ClearanceError):
            self._submit()

    def test_notifications_and_audit_created(self):
        req = self._submit()
        self.assertTrue(self.student.notifications.exists())
        self.assertTrue(self.lib_o.notifications.exists())
        services.decide(self.lib_o, self._step(req, self.lib), True)
        self.assertTrue(req.steps.get(department=self.lib).officer == self.lib_o)
        self.assertTrue(ClearanceRequest.objects.get(pk=req.pk).student.requests.exists())


class AccessTests(WorkflowTests):
    def test_student_cannot_open_officer_or_admin_pages(self):
        self.client.login(username="S1", password="pw")
        self.assertEqual(self.client.get(reverse("officer_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("manage_dashboard")).status_code, 403)

    def test_officer_cannot_open_admin_pages(self):
        self.client.login(username="lib", password="pw")
        self.assertEqual(self.client.get(reverse("manage_reports")).status_code, 403)

    def test_anonymous_redirected_to_login(self):
        self.assertEqual(self.client.get(reverse("student_dashboard")).status_code, 302)

    def test_dashboards_render_for_each_role(self):
        self._submit()
        for user, name in (("S1", "student_dashboard"), ("lib", "officer_dashboard"), ("adm", "manage_dashboard"),
                           ("adm", "manage_reports"), ("adm", "manage_officers"), ("adm", "manage_audit")):
            self.client.login(username=user, password="pw")
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_review_and_decide_through_the_web(self):
        req = self._submit()
        step = self._step(req, self.lib)
        self.client.login(username="lib", password="pw")
        self.assertEqual(self.client.get(reverse("officer_review", args=[step.pk])).status_code, 200)
        resp = self.client.post(reverse("officer_review", args=[step.pk]), {"decision": "approve", "comment": "ok"})
        self.assertEqual(resp.status_code, 302)
        step.refresh_from_db()
        self.assertEqual(step.status, ApprovalStep.Status.APPROVED)

    def test_verify_page_and_certificate_download_permissions(self):
        req = self._submit()
        services.decide(self.lib_o, self._step(req, self.lib), True)
        services.decide(self.fin_o, self._step(req, self.fin), True)
        services.decide(self.cs_o, self._step(req, self.sch), True)
        cert = Certificate.objects.get(request=req)
        self.assertContains(self.client.get(reverse("verify", args=[cert.code])), "valid")
        self.assertContains(self.client.get(reverse("verify", args=["SCMS-FAKE"])), "not found")
        self.client.login(username="S1", password="pw")
        self.assertEqual(self.client.get(reverse("certificate", args=[req.pk]) + "?format=html").status_code, 200)
        self.client.login(username="lib", password="pw")
        self.assertEqual(self.client.get(reverse("certificate", args=[req.pk])).status_code, 403)

    def test_report_counts(self):
        self._submit()
        report = services.build_report()
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["counts"]["waiting"], 1)
