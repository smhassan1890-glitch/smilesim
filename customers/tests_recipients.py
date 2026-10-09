from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from companies.models import Company, Product, ProductLine
from customers.forms import CustomerPaymentForm
from customers.models import CustomerPayment, CustomerPaymentSubmission
from customers.services import (
    approve_customer_payment_submission,
    approve_sale,
    create_customer,
    delete_customer_payment,
    record_customer_payment,
    submit_customer_payment_submission,
    sync_on_account_charge_for_sale,
)
from sales.models import PaymentMethod, PaymentRecipient, Sale
from sales.services import create_sale, update_sale_fields

User = get_user_model()


class CustomerPaymentRecipientTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from accounts.models import UserProfile

        cls.user = User.objects.create_user("mgr_rcp", password="x")
        UserProfile.objects.update_or_create(
            user=cls.user,
            defaults={"role": UserProfile.Role.MANAGEMENT, "is_active_profile": True},
        )
        cls.emp = User.objects.create_user("emp_rcp", password="x")
        UserProfile.objects.update_or_create(
            user=cls.emp,
            defaults={"role": UserProfile.Role.EMPLOYEE, "is_active_profile": True},
        )
        cls.company = Company.objects.create(
            name="Co", opening_balance=Decimal("10000"), current_balance=Decimal("10000")
        )
        cls.line = ProductLine.objects.create(company=cls.company, name="L")
        cls.product = Product.objects.create(
            line=cls.line,
            variant_label="P",
            cost_price=Decimal("5"),
            default_sell_price=Decimal("200"),
        )
        cls.jawwal = PaymentMethod.objects.create(name="Jawwal Pay")
        cls.ahmad = PaymentRecipient.objects.create(payment_method=cls.jawwal, name="Ahmad")
        cls.sami = PaymentRecipient.objects.create(payment_method=cls.jawwal, name="Sami")

    def setUp(self):
        self.customer = create_customer(name="Hazem", user=self.user)

    def _settled_sale(self, sell):
        sale = create_sale(
            company=self.company,
            product=self.product,
            reference_number=f"059-{sell}",
            payer_name=self.customer.name,
            payment_method=None,
            sell_price_actual=Decimal(sell),
            notes="",
            user=self.user,
            on_account=True,
            customer=self.customer,
        )
        approve_sale(sale=sale, user=self.user)
        return sale

    def _pay(self, amount, recipient):
        return record_customer_payment(
            customer=self.customer,
            amount=Decimal(amount),
            payment_method=self.jawwal,
            payment_recipient=recipient,
            user=self.user,
        )


class RecordPaymentRecipientTests(CustomerPaymentRecipientTestCase):
    def test_record_payment_stores_recipient(self):
        payment = self._pay("30", self.sami)
        payment.refresh_from_db()
        self.assertEqual(payment.payment_recipient_id, self.sami.pk)

    def test_record_payment_requires_choice_for_multi_recipient_method(self):
        with self.assertRaises(ValueError):
            self._pay("30", None)
        self.assertFalse(CustomerPayment.objects.exists())

    def test_record_payment_auto_assigns_single_recipient(self):
        self.sami.is_active = False
        self.sami.save(update_fields=["is_active"])
        payment = self._pay("30", None)
        self.assertEqual(payment.payment_recipient_id, self.ahmad.pk)

    def test_paid_via_employee_payment_has_no_recipient(self):
        from employees.models import EmployeeProfile

        profile = EmployeeProfile.objects.create(user=self.emp, monthly_salary=Decimal("0"))
        payment = record_customer_payment(
            customer=self.customer,
            amount=Decimal("30"),
            payment_method=None,
            user=self.user,
            paid_via_employee=True,
            employee_recipient=profile,
        )
        self.assertIsNone(payment.payment_recipient_id)


class SubmissionRecipientTests(CustomerPaymentRecipientTestCase):
    def test_submission_then_approval_copies_recipient(self):
        sub = submit_customer_payment_submission(
            customer=self.customer,
            amount=Decimal("40"),
            payment_method=self.jawwal,
            payment_recipient=self.ahmad,
            user=self.emp,
        )
        self.assertEqual(sub.payment_recipient_id, self.ahmad.pk)
        payment = approve_customer_payment_submission(submission=sub, user=self.user)
        self.assertEqual(payment.payment_recipient_id, self.ahmad.pk)

    def test_submission_requires_choice_for_multi_recipient_method(self):
        with self.assertRaises(ValueError):
            submit_customer_payment_submission(
                customer=self.customer,
                amount=Decimal("40"),
                payment_method=self.jawwal,
                user=self.emp,
            )
        self.assertFalse(CustomerPaymentSubmission.objects.exists())

    def test_approval_keeps_recipient_deactivated_after_submission(self):
        sub = submit_customer_payment_submission(
            customer=self.customer,
            amount=Decimal("40"),
            payment_method=self.jawwal,
            payment_recipient=self.ahmad,
            user=self.emp,
        )
        self.ahmad.is_active = False
        self.ahmad.save(update_fields=["is_active"])
        payment = approve_customer_payment_submission(submission=sub, user=self.user)
        self.assertEqual(payment.payment_recipient_id, self.ahmad.pk)

    def _legacy_submission(self):
        return CustomerPaymentSubmission.objects.create(
            customer=self.customer,
            amount=Decimal("40"),
            payment_method=self.jawwal,
            created_by=self.emp,
            status=CustomerPaymentSubmission.Status.AWAITING,
        )

    def test_approve_legacy_submission_without_recipient_multi_recipient_method(self):
        sub = self._legacy_submission()
        payment = approve_customer_payment_submission(submission=sub, user=self.user)
        payment.refresh_from_db()
        self.assertIsNone(payment.payment_recipient_id)
        sub.refresh_from_db()
        self.assertEqual(sub.status, CustomerPaymentSubmission.Status.APPROVED)

    def test_approve_legacy_submission_without_recipient_single_recipient_method(self):
        sub = self._legacy_submission()
        self.sami.is_active = False
        self.sami.save(update_fields=["is_active"])
        payment = approve_customer_payment_submission(submission=sub, user=self.user)
        payment.refresh_from_db()
        self.assertEqual(payment.payment_recipient_id, self.ahmad.pk)


class SettlementRecipientTests(CustomerPaymentRecipientTestCase):
    def test_fifo_settlement_copies_recipient_to_sales(self):
        sale = self._settled_sale("50")
        self._pay("50", self.sami)
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.PAID)
        self.assertEqual(sale.payment_method_id, self.jawwal.pk)
        self.assertEqual(sale.payment_recipient_id, self.sami.pk)

    def test_delete_payment_clears_recipient_on_settled_sales(self):
        s1 = self._settled_sale("50")
        s2 = self._settled_sale("30")
        payment = self._pay("80", self.sami)
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertEqual(s1.payment_recipient_id, self.sami.pk)
        self.assertEqual(s2.payment_recipient_id, self.sami.pk)

        delete_customer_payment(payment=payment, user=self.user)

        for sale in (s1, s2):
            sale.refresh_from_db()
            self.assertEqual(sale.status, Sale.Status.PENDING)
            self.assertIsNone(sale.payment_method_id)
            self.assertIsNone(sale.payment_recipient_id)

    def test_price_edit_unsettle_clears_recipient(self):
        sale = self._settled_sale("50")
        self._pay("50", self.sami)
        sale.refresh_from_db()
        self.assertEqual(sale.payment_recipient_id, self.sami.pk)

        update_sale_fields(
            sale=sale,
            payment_method=None,
            payment_recipient=None,
            payer_name=sale.payer_name,
            reference_number=sale.reference_number,
            sell_price_actual=Decimal("60"),
            notes="",
            user=self.user,
        )

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.PENDING)
        self.assertIsNone(sale.payment_method_id)
        self.assertIsNone(sale.payment_recipient_id)

    def test_charge_sync_reset_clears_recipient(self):
        sale = self._settled_sale("50")
        self._pay("50", self.sami)
        Sale.objects.filter(pk=sale.pk).update(sell_price_actual=Decimal("60"))

        sync_on_account_charge_for_sale(sale=sale, user=self.user)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.PENDING)
        self.assertIsNone(sale.payment_method_id)
        self.assertIsNone(sale.payment_recipient_id)


class EmployeeModalRecipientTests(CustomerPaymentRecipientTestCase):
    def setUp(self):
        from core.models import AppSettings

        super().setUp()
        AppSettings.objects.update_or_create(
            pk=1,
            defaults={
                "require_settlement_request_approval": True,
                "sales_show_record_payment": True,
            },
        )
        self.client.force_login(self.emp)

    def _post(self, **extra):
        data = {
            "customer": str(self.customer.pk),
            "amount": "25.00",
            "payment_method": str(self.jawwal.pk),
        }
        data.update(extra)
        return self.client.post(
            reverse("sales:employee_submit_customer_payment_submission"), data
        )

    def test_employee_modal_post_requires_choice(self):
        response = self._post()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CustomerPaymentSubmission.objects.exists())
        texts = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("Pick who received the payment." in t for t in texts), texts)

    def test_employee_modal_post_stores_recipient(self):
        response = self._post(payment_recipient=str(self.sami.pk))
        self.assertEqual(response.status_code, 302)
        sub = CustomerPaymentSubmission.objects.get()
        self.assertEqual(sub.payment_recipient_id, self.sami.pk)

    def test_employee_modal_post_rejects_foreign_recipient(self):
        cash = PaymentMethod.objects.create(name="Cash")
        response = self._post(
            payment_method=str(cash.pk), payment_recipient=str(self.sami.pk)
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CustomerPaymentSubmission.objects.exists())

    def _submission_form(self, **extra):
        from customers.forms import EmployeeCustomerPaymentSubmissionForm

        data = {
            "customer": str(self.customer.pk),
            "amount": "25.00",
            "payment_method": str(self.jawwal.pk),
        }
        data.update(extra)
        return EmployeeCustomerPaymentSubmissionForm(data=data, user=self.emp)

    def test_submission_form_invalid_recipient_id_reports_single_error(self):
        form = self._submission_form(payment_recipient="999999")
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors["payment_recipient"]), 1, form.errors)

    def test_submission_form_paid_via_employee_ignores_stale_recipient(self):
        from core.models import AppSettings
        from employees.models import EmployeeProfile

        AppSettings.objects.update_or_create(
            pk=1, defaults={"sales_show_employee_payment": True}
        )
        EmployeeProfile.objects.create(user=self.emp, monthly_salary=Decimal("0"))
        self.emp.refresh_from_db()
        self.sami.is_active = False
        self.sami.save(update_fields=["is_active"])

        form = self._submission_form(
            paid_via_employee="True", payment_method="", payment_recipient=str(self.sami.pk)
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["payment_recipient"])

    def test_entry_page_renders_modal_recipient_picker(self):
        response = self.client.get(reverse("sales:employee_entry"))
        self.assertContains(response, 'id="rd-pay-sub-recipient-picker"')
        self.assertContains(response, 'id="id_pay_sub_payment_recipient"')


class ManagementPaymentRecipientTests(CustomerPaymentRecipientTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_form_requires_choice_for_multi_recipient_method(self):
        form = CustomerPaymentForm(
            data={"amount": "10", "payment_method": str(self.jawwal.pk)}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("payment_recipient", form.errors)

    def test_form_invalid_recipient_id_reports_single_error(self):
        form = CustomerPaymentForm(
            data={
                "amount": "10",
                "payment_method": str(self.jawwal.pk),
                "payment_recipient": "999999",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors["payment_recipient"]), 1, form.errors)

    def test_form_recipient_options_carry_method(self):
        html = str(CustomerPaymentForm()["payment_recipient"])
        self.assertIn(f'data-method="{self.jawwal.pk}"', html)
        self.assertIn('data-recipient-for="id_payment_method"', html)

    def test_record_payment_view_stores_recipient(self):
        response = self.client.post(
            reverse("customers:customer_record_payment", args=[self.customer.pk]),
            {
                "amount": "15",
                "payment_method": str(self.jawwal.pk),
                "payment_recipient": str(self.ahmad.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        payment = CustomerPayment.objects.get()
        self.assertEqual(payment.payment_recipient_id, self.ahmad.pk)

    def test_detail_page_renders_recipient_select_and_filter_script(self):
        response = self.client.get(
            reverse("customers:customer_detail", args=[self.customer.pk])
        )
        self.assertContains(response, 'name="payment_recipient"')
        self.assertContains(response, "js/recipient-select-filter.js")

    def test_submissions_list_shows_recipient(self):
        submit_customer_payment_submission(
            customer=self.customer,
            amount=Decimal("40"),
            payment_method=self.jawwal,
            payment_recipient=self.ahmad,
            user=self.emp,
        )
        response = self.client.get(reverse("customers:customer_payment_submissions_list"))
        self.assertContains(response, "Ahmad")
