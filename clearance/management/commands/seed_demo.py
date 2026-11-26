from django.core.management.base import BaseCommand

from accounts.models import Department, School, User

OFFICES = [("Library", 1, False), ("Finance", 2, False), ("Accommodation", 3, False), ("Registry", 4, False), ("School", 5, True)]
SCHOOLS = ["School of Computing", "School of Business"]


class Command(BaseCommand):
    help = "Create demo schools, offices and users (safe to run more than once)."

    def handle(self, *args, **opts):
        schools = [School.objects.get_or_create(name=n)[0] for n in SCHOOLS]
        depts = {}
        for name, order, is_school in OFFICES:
            depts[name] = Department.objects.get_or_create(name=name, defaults={"order": order, "is_school_office": is_school})[0]

        def user(username, password, role, **extra):
            u, created = User.objects.get_or_create(username=username, defaults={"role": role, **extra})
            if created:
                u.set_password(password)
                if role == User.Role.ADMIN:
                    u.is_superuser = True
                u.save()
            return u

        user("admin", "Admin@12345", User.Role.ADMIN, first_name="System", last_name="Admin", email="admin@university.local")
        for name in ("Library", "Finance", "Accommodation", "Registry"):
            user(f"{name.lower()}_officer", "Officer@12345", User.Role.OFFICER, first_name=name, last_name="Officer",
                 email=f"{name.lower()}@university.local", department=depts[name])
        user("computing_officer", "Officer@12345", User.Role.OFFICER, first_name="Computing", last_name="Officer",
             email="computing@university.local", department=depts["School"], school=schools[0])
        user("business_officer", "Officer@12345", User.Role.OFFICER, first_name="Business", last_name="Officer",
             email="business@university.local", department=depts["School"], school=schools[1])
        user("CS/001/2022", "Student@12345", User.Role.STUDENT, first_name="Amina", last_name="Otieno",
             email="amina@student.local", school=schools[0])

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("Admin:    admin / Admin@12345")
        self.stdout.write("Officers: library_officer, finance_officer, accommodation_officer, registry_officer,")
        self.stdout.write("          computing_officer, business_officer  (password Officer@12345)")
        self.stdout.write("Student:  CS/001/2022 / Student@12345")
