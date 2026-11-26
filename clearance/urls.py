from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    # student
    path("student/", views.student_dashboard, name="student_dashboard"),
    path("student/apply/", views.apply, name="apply"),
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("requests/<int:pk>/resubmit/", views.resubmit, name="resubmit"),
    path("requests/<int:pk>/document/", views.document_download, name="document_download"),
    path("requests/<int:pk>/certificate/", views.certificate, name="certificate"),
    # officer
    path("officer/", views.officer_dashboard, name="officer_dashboard"),
    path("officer/history/", views.officer_history, name="officer_history"),
    path("officer/review/<int:step_id>/", views.officer_review, name="officer_review"),
    # administrator
    path("manage/", views.manage_dashboard, name="manage_dashboard"),
    path("manage/reports/", views.manage_reports, name="manage_reports"),
    path("manage/reports/export/", views.manage_reports_csv, name="manage_reports_csv"),
    path("manage/officers/", views.manage_officers, name="manage_officers"),
    path("manage/audit/", views.manage_audit, name="manage_audit"),
    # shared / public
    path("notifications/", views.notification_list, name="notifications"),
    path("verify/", views.verify, name="verify_form"),
    path("verify/<str:code>/", views.verify, name="verify"),
]
