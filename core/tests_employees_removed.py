from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db import connection
from django.test import TestCase

from accounts.models import UserProfile
from core.models import AppSettings
from customers.models import CustomerPayment, CustomerPaymentSubmission
from sales.models import Sale

User = get_user_model()


class EmployeesAppRemovedTests(TestCase):
    def test_employees_app_not_installed(self):
        self.assertFalse(apps.is_installed("employees"))

    def test_employee_payment_fields_removed(self):
        cases = [
            (Sale, "paid_via_employee"),
            (Sale, "employee_recipient"),
            (CustomerPayment, "paid_via_employee"),
            (CustomerPayment, "employee_recipient"),
            (CustomerPaymentSubmission, "paid_via_employee"),
            (CustomerPaymentSubmission, "employee_recipient"),
            (AppSettings, "sales_show_employee_payment"),
        ]
        for model, name in cases:
            with self.subTest(model=model.__name__, field=name):
                with self.assertRaises(FieldDoesNotExist):
                    model._meta.get_field(name)

    def test_employees_tables_absent(self):
        tables = connection.introspection.table_names()
        self.assertFalse([t for t in tables if t.startswith("employees_")])

    def test_employees_pages_gone(self):
        mgr = User.objects.create_user("removed_mgr", password="x")
        UserProfile.objects.update_or_create(
            user=mgr,
            defaults={"role": UserProfile.Role.MANAGEMENT, "is_active_profile": True},
        )
        self.client.force_login(mgr)

        self.assertEqual(self.client.get("/employees/").status_code, 404)

    def test_sales_entry_has_no_employee_payment_option(self):
        emp = User.objects.create_user("removed_emp", password="x")
        UserProfile.objects.update_or_create(
            user=emp,
            defaults={"role": UserProfile.Role.EMPLOYEE, "is_active_profile": True},
        )
        self.client.force_login(emp)

        response = self.client.get("/employee/sales/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "paid_via_employee")
