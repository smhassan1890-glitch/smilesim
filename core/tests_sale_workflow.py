"""Auto-approval workflow tests driven by AppSettings."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from companies.models import Company, Product, ProductLine
from core.models import AppSettings
from core.sale_workflow import finalize_payment_submission_after_entry, finalize_sale_after_entry
from customers.models import Customer, CustomerPaymentSubmission
from customers.services import submit_customer_payment_submission
from sales.models import PaymentMethod, Sale
from sales.services import create_sale

User = get_user_model()


class SaleWorkflowSettingsTests(TestCase):
    _DEFAULT_WORKFLOW = {
        "require_debt_request_approval": True,
        "require_settlement_request_approval": True,
        "require_payment_request_approval": True,
    }

    def tearDown(self):
        AppSettings.objects.update_or_create(pk=1, defaults=self._DEFAULT_WORKFLOW)

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("wf", password="x")
        UserProfile.objects.update_or_create(
            user=cls.user,
            defaults={"role": UserProfile.Role.MANAGEMENT, "is_active_profile": True},
        )
        cls.company = Company.objects.create(name="Co", opening_balance=Decimal("1000"))
        line = ProductLine.objects.create(company=cls.company, name="Line")
        cls.product = Product.objects.create(
            line=line,
            cost_price=Decimal("10"),
            default_sell_price=Decimal("20"),
        )
        cls.pm = PaymentMethod.objects.create(name="Cash")
        cls.customer = Customer.objects.create(name="Ali", created_by=cls.user)

    def _cash_sale(self):
        return create_sale(
            company=self.company,
            product=self.product,
            reference_number="0501111111",
            payer_name="Walk-in",
            payment_method=self.pm,
            sell_price_actual=Decimal("20"),
            notes="",
            user=self.user,
        )

    def _on_account_sale(self):
        return create_sale(
            company=self.company,
            product=self.product,
            reference_number="0502222222",
            payer_name=self.customer.name,
            payment_method=None,
            sell_price_actual=Decimal("30"),
            notes="",
            user=self.user,
            on_account=True,
            customer=self.customer,
        )

    def test_cash_auto_paid_when_payment_approval_off(self):
        AppSettings.objects.update_or_create(
            pk=1,
            defaults={"require_payment_request_approval": False},
        )
        sale = self._cash_sale()
        outcome = finalize_sale_after_entry(sale=sale, user=self.user, on_account=False)
        sale.refresh_from_db()
        self.assertEqual(outcome, "paid")
        self.assertEqual(sale.status, Sale.Status.PAID)

    def test_on_account_auto_posted_when_debt_approval_off(self):
        AppSettings.objects.update_or_create(
            pk=1,
            defaults={"require_debt_request_approval": False},
        )
        sale = self._on_account_sale()
        outcome = finalize_sale_after_entry(sale=sale, user=self.user, on_account=True)
        sale.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(outcome, "posted_debt")
        self.assertEqual(sale.status, Sale.Status.PENDING)
        self.assertEqual(self.customer.current_balance, Decimal("30"))

    def test_cash_stays_pending_when_payment_approval_on(self):
        AppSettings.objects.update_or_create(
            pk=1,
            defaults={"require_payment_request_approval": True},
        )
        sale = self._cash_sale()
        outcome = finalize_sale_after_entry(sale=sale, user=self.user, on_account=False)
        sale.refresh_from_db()
        self.assertEqual(outcome, "pending_payment")
        self.assertEqual(sale.status, Sale.Status.PENDING)

    def test_settlement_auto_applied_when_approval_off(self):
        AppSettings.objects.update_or_create(
            pk=1,
            defaults={"require_settlement_request_approval": False},
        )
        sub = submit_customer_payment_submission(
            customer=self.customer,
            amount=Decimal("15"),
            payment_method=self.pm,
            notes="",
            user=self.user,
        )
        applied = finalize_payment_submission_after_entry(submission=sub, user=self.user)
        sub.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertTrue(applied)
        self.assertEqual(sub.status, CustomerPaymentSubmission.Status.APPROVED)
        self.assertEqual(self.customer.current_balance, Decimal("-15"))

    def test_settlement_queued_when_approval_on(self):
        AppSettings.objects.update_or_create(
            pk=1,
            defaults={"require_settlement_request_approval": True},
        )
        sub = submit_customer_payment_submission(
            customer=self.customer,
            amount=Decimal("50"),
            payment_method=self.pm,
            notes="",
            user=self.user,
        )
        applied = finalize_payment_submission_after_entry(submission=sub, user=self.user)
        sub.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertFalse(applied)
        self.assertEqual(sub.status, CustomerPaymentSubmission.Status.AWAITING)
        self.assertEqual(self.customer.current_balance, Decimal("0"))