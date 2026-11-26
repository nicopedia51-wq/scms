from django import forms
from django.conf import settings

from accounts.models import Department, School

from .models import ClearanceRequest


class ClearanceRequestForm(forms.ModelForm):
    class Meta:
        model = ClearanceRequest
        fields = ("reason", "academic_year", "document")
        widgets = {
            "reason": forms.Select(attrs={"class": "form-select"}),
            "academic_year": forms.TextInput(attrs={"class": "form-control", "placeholder": "2025/2026"}),
            "document": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
        labels = {"document": "Supporting document (optional)"}

    def clean_academic_year(self):
        value = self.cleaned_data["academic_year"].strip()
        parts = value.split("/")
        if len(parts) != 2 or not all(p.isdigit() and len(p) == 4 for p in parts) or int(parts[1]) != int(parts[0]) + 1:
            raise forms.ValidationError("Use the format 2025/2026.")
        return value

    def clean_document(self):
        return _validate_upload(self.cleaned_data.get("document"))


class ResubmitForm(forms.Form):
    document = forms.FileField(required=False, label="Updated document (optional)",
                               widget=forms.ClearableFileInput(attrs={"class": "form-control"}))

    def clean_document(self):
        return _validate_upload(self.cleaned_data.get("document"))


def _validate_upload(f):
    if not f:
        return f
    if f.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise forms.ValidationError(f"File is too large (maximum {settings.MAX_UPLOAD_MB} MB).")
    if not f.name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
        raise forms.ValidationError("Upload a PDF, PNG or JPG file.")
    return f


class DecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=[("approve", "Approve"), ("reject", "Reject")], widget=forms.RadioSelect)
    comment = forms.CharField(required=False, label="Comment", widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))


class ReportFilterForm(forms.Form):
    school = forms.ModelChoiceField(School.objects.all(), required=False, empty_label="All schools",
                                    widget=forms.Select(attrs={"class": "form-select"}))
    department = forms.ModelChoiceField(Department.objects.all(), required=False, empty_label="All offices",
                                        label="Waiting at", widget=forms.Select(attrs={"class": "form-select"}))
    date_from = forms.DateField(required=False, label="From", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    date_to = forms.DateField(required=False, label="To", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
