# Student Clearance Management System (SCMS)

Django web system for online student clearance: students apply, five offices approve in order
(Library > Finance > Accommodation > Registry > School), and a PDF certificate with a verification code is issued.

## 1. Setup in VS Code (Windows / Mac / Linux)

Open the `scms` folder in VS Code, open the terminal (Ctrl + `) and run:

```
python -m venv venv
venv\Scripts\activate          # Windows      (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo     # demo offices and users
python manage.py runserver
```
Open http://127.0.0.1:8000

If `pip install` fails on WeasyPrint, remove that line from requirements.txt. Everything still works:
the certificate then opens as a printable page (Print > Save as PDF).

## 2. Demo logins (created by `seed_demo`)

| Role | Username | Password |
|---|---|---|
| Administrator | admin | Admin@12345 |
| Student | CS/001/2022 | Student@12345 |
| Officers | library_officer, finance_officer, accommodation_officer, registry_officer, computing_officer, business_officer | Officer@12345 |

Change these passwords before any real use. New students register themselves (username = registration number).

## 3. Try the workflow
1. Log in as the student > Apply. 2. Log in as `library_officer` > Awaiting decision > Review > Approve.
3. Repeat for finance, accommodation, registry, computing (school office). 4. Student downloads the certificate.
Try Reject (a reason is required) and Resubmit. Admin: Overview, Reports (filters + CSV), Officers, Audit log.
Emails print in the terminal (console backend).

## 4. Run the tests
```
python manage.py test
```

## 5. PostgreSQL instead of SQLite
`pip install psycopg2-binary`, create a database, then set environment variables before `migrate`:
`DB_ENGINE=postgres DB_NAME=scms DB_USER=postgres DB_PASSWORD=... DB_HOST=localhost`

## 6. Project map
- `accounts/` users, roles, School, Department, registration, role decorator
- `clearance/models.py` ClearanceRequest, ApprovalStep, Certificate, Notification, AuditLog
- `clearance/services.py` ALL business rules (sequence, reject/resubmit, certificate eligibility, reports)
- `clearance/views.py` student / officer / admin pages; `clearance/tests.py` unit + access tests
- `templates/`, `static/` HTML, CSS, JS

## 7. Going live
Set `DJANGO_DEBUG=0`, a real `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, host behind HTTPS, run
`python manage.py collectstatic`, and configure real SMTP (`EMAIL_BACKEND`).
# scms
