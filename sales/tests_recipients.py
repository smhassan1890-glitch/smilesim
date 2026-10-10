import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from companies.models import Company, Product, ProductLine
from sales.models import PaymentMethod, PaymentRecipient, Sale
from sales.recipients import recipients_json, resolve_payment_recipient
from sales.services import create_sale, update_sale_fields

User = get_user_model()


class PaymentRecipientModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("recip_user", password="x")
        cls.company = Company.objects.create(
            name="RecipCo",
            opening_balance=Decimal("1000"),
            current_balance=Decimal("1000"),
        )
        cls.line = ProductLine.objects.create(company=cls.company, name="L")
        cls.product = Product.objects.create(
            line=cls.line,
            variant_label="P",
            cost_price=Decimal("5"),
            default_sell_price=Decimal("20"),
        )
        cls.pm = PaymentMethod.objects.create(name="Jawwal Pay")

    def test_active_recipients_ordered_and_filtered(self):
        PaymentRecipient.objects.create(payment_method=self.pm, name="رامز", sort_order=2)
        PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد", sort_order=1)
        PaymentRecipient.objects.create(
            payment_method=self.pm, name="رائد", sort_order=1, is_active=False
        )

        self.assertEqual([r.name for r in self.pm.active_recipients()], ["أحمد", "رامز"])

    def test_duplicate_name_same_method_rejected(self):
        PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد")

    def test_used_recipient_cannot_be_deleted(self):
        r = PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد")
        sale = create_sale(
            company=self.company,
            product=self.product,
            reference_number="0599000000",
            payer_name="Ali",
            payment_method=self.pm,
            sell_price_actual=Decimal("20"),
            notes="",
            user=self.user,
        )
        Sale.objects.filter(pk=sale.pk).update(payment_recipient=r)

        with self.assertRaises(ProtectedError):
            r.delete()


class ResolvePaymentRecipientTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pm = PaymentMethod.objects.create(name="Jawwal Pay")
        cls.other_pm = PaymentMethod.objects.create(name="Bank of Palestine")

    def test_none_method_returns_none(self):
        self.assertIsNone(resolve_payment_recipient(None, None))

    def test_no_recipients_returns_none(self):
        self.assertIsNone(resolve_payment_recipient(self.pm, None))

    def test_single_recipient_auto_assigned(self):
        r = PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد")

        self.assertEqual(resolve_payment_recipient(self.pm, None), r)
        self.assertEqual(resolve_payment_recipient(self.pm, r), r)

    def test_many_requires_choice(self):
        PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد")
        PaymentRecipient.objects.create(payment_method=self.pm, name="رامز")

        with self.assertRaisesMessage(ValueError, "Pick who received the payment."):
            resolve_payment_recipient(self.pm, None)

    def test_many_returns_chosen(self):
        PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد")
        b = PaymentRecipient.objects.create(payment_method=self.pm, name="رامز")

        self.assertEqual(resolve_payment_recipient(self.pm, b), b)

    def test_rejects_recipient_of_other_method(self):
        PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد")
        PaymentRecipient.objects.create(payment_method=self.pm, name="رامز")
        foreign = PaymentRecipient.objects.create(payment_method=self.other_pm, name="رائد")

        with self.assertRaisesMessage(
            ValueError, "Selected recipient does not belong to this payment method."
        ):
            resolve_payment_recipient(self.pm, foreign)

    def test_rejects_recipient_when_method_has_no_recipients(self):
        foreign = PaymentRecipient.objects.create(payment_method=self.other_pm, name="رائد")

        with self.assertRaisesMessage(
            ValueError, "Selected recipient does not belong to this payment method."
        ):
            resolve_payment_recipient(self.pm, foreign)

    def test_rejects_inactive_recipient(self):
        PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد")
        inactive = PaymentRecipient.objects.create(
            payment_method=self.pm, name="رامز", is_active=False
        )

        with self.assertRaisesMessage(
            ValueError, "Selected recipient does not belong to this payment method."
        ):
            resolve_payment_recipient(self.pm, inactive)

    def test_recipients_json_lists_active_only(self):
        a = PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد")
        PaymentRecipient.objects.create(payment_method=self.pm, name="رامز", is_active=False)

        raw = recipients_json(self.pm)

        self.assertEqual(json.loads(raw), [{"id": a.pk, "name": "أحمد"}])
        self.assertIn("أحمد", raw)


class PaymentMethodRecipientsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("mgr_recip", password="x")
        UserProfile.objects.update_or_create(
            user=cls.user,
            defaults={"role": UserProfile.Role.MANAGEMENT, "is_active_profile": True},
        )
        cls.company = Company.objects.create(
            name="RecipViewCo",
            opening_balance=Decimal("1000"),
            current_balance=Decimal("1000"),
        )
        cls.line = ProductLine.objects.create(company=cls.company, name="L")
        cls.product = Product.objects.create(
            line=cls.line,
            variant_label="P",
            cost_price=Decimal("5"),
            default_sell_price=Decimal("20"),
        )

    def setUp(self):
        self.client.force_login(self.user)

    @staticmethod
    def _management(total, initial=0):
        return {
            "recipients-TOTAL_FORMS": str(total),
            "recipients-INITIAL_FORMS": str(initial),
            "recipients-MIN_NUM_FORMS": "0",
            "recipients-MAX_NUM_FORMS": "1000",
        }

    def test_create_with_recipients(self):
        data = {"name": "Jawwal Pay", "is_active": "on", **self._management(3)}
        for i, name in enumerate(["أحمد", "رائد", "رامز"]):
            data[f"recipients-{i}-name"] = name
            data[f"recipients-{i}-sort_order"] = str(i)
            data[f"recipients-{i}-is_active"] = "on"

        response = self.client.post(reverse("sales:payment_method_create"), data)

        self.assertRedirects(
            response, reverse("sales:payment_method_list"), fetch_redirect_response=False
        )
        pm = PaymentMethod.objects.get(name="Jawwal Pay")
        self.assertEqual(pm.recipients.count(), 3)
        self.assertEqual([r.name for r in pm.active_recipients()], ["أحمد", "رائد", "رامز"])

    def test_edit_renames_and_deactivates(self):
        pm = PaymentMethod.objects.create(name="Jawwal Pay")
        a = PaymentRecipient.objects.create(payment_method=pm, name="أحمد", sort_order=0)
        b = PaymentRecipient.objects.create(payment_method=pm, name="رامز", sort_order=1)
        data = {
            "name": "Jawwal Pay",
            "is_active": "on",
            **self._management(2, initial=2),
            "recipients-0-id": str(a.pk),
            "recipients-0-name": "أحمد علي",
            "recipients-0-sort_order": "0",
            "recipients-0-is_active": "on",
            "recipients-1-id": str(b.pk),
            "recipients-1-name": "رامز",
            "recipients-1-sort_order": "1",
        }

        response = self.client.post(reverse("sales:payment_method_edit", args=[pm.pk]), data)

        self.assertRedirects(
            response, reverse("sales:payment_method_list"), fetch_redirect_response=False
        )
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.name, "أحمد علي")
        self.assertTrue(a.is_active)
        self.assertFalse(b.is_active)

    def test_delete_used_recipient_is_refused(self):
        pm = PaymentMethod.objects.create(name="Jawwal Pay")
        used = PaymentRecipient.objects.create(payment_method=pm, name="أحمد")
        sale = create_sale(
            company=self.company,
            product=self.product,
            reference_number="0599000000",
            payer_name="Ali",
            payment_method=pm,
            sell_price_actual=Decimal("20"),
            notes="",
            user=self.user,
        )
        Sale.objects.filter(pk=sale.pk).update(payment_recipient=used)
        data = {
            "name": "Jawwal Pay Wallet",
            "is_active": "on",
            **self._management(2, initial=1),
            "recipients-0-id": str(used.pk),
            "recipients-0-name": "أحمد",
            "recipients-0-sort_order": "0",
            "recipients-0-is_active": "on",
            "recipients-0-DELETE": "on",
            "recipients-1-name": "رامز",
            "recipients-1-sort_order": "1",
            "recipients-1-is_active": "on",
        }

        response = self.client.post(
            reverse("sales:payment_method_edit", args=[pm.pk]), data, follow=True
        )

        self.assertTrue(PaymentRecipient.objects.filter(pk=used.pk).exists())
        self.assertContains(response, "is used by existing records")
        pm.refresh_from_db()
        self.assertEqual(pm.name, "Jawwal Pay Wallet")
        self.assertTrue(pm.recipients.filter(name="رامز").exists())

    def test_delete_unused_recipient(self):
        pm = PaymentMethod.objects.create(name="Jawwal Pay")
        unused = PaymentRecipient.objects.create(payment_method=pm, name="رائد")
        data = {
            "name": "Jawwal Pay",
            "is_active": "on",
            **self._management(1, initial=1),
            "recipients-0-id": str(unused.pk),
            "recipients-0-name": "رائد",
            "recipients-0-sort_order": "0",
            "recipients-0-is_active": "on",
            "recipients-0-DELETE": "on",
        }

        self.client.post(reverse("sales:payment_method_edit", args=[pm.pk]), data)

        self.assertFalse(PaymentRecipient.objects.filter(pk=unused.pk).exists())

    def test_edit_page_renders_recipient_formset(self):
        pm = PaymentMethod.objects.create(name="Jawwal Pay")
        PaymentRecipient.objects.create(payment_method=pm, name="أحمد")

        response = self.client.get(reverse("sales:payment_method_edit", args=[pm.pk]))

        self.assertContains(response, 'name="recipients-TOTAL_FORMS"')
        self.assertContains(response, 'id="recipient-empty-form"')
        self.assertContains(response, 'value="أحمد"')

    def test_list_shows_active_recipient_names(self):
        pm = PaymentMethod.objects.create(name="Jawwal Pay")
        PaymentRecipient.objects.create(payment_method=pm, name="أحمد")
        PaymentRecipient.objects.create(payment_method=pm, name="رائد", is_active=False)

        response = self.client.get(reverse("sales:payment_method_list"))

        self.assertContains(response, "أحمد")
        self.assertNotContains(response, "رائد")


class EmployeeEntryRecipientTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from customers.models import Customer

        cls.company = Company.objects.create(
            name="EntryRecipCo",
            opening_balance=Decimal("1000"),
            current_balance=Decimal("1000"),
        )
        cls.line = ProductLine.objects.create(company=cls.company, name="L")
        cls.product = Product.objects.create(
            line=cls.line,
            variant_label="P",
            cost_price=Decimal("5"),
            default_sell_price=Decimal("10"),
        )
        cls.pm = PaymentMethod.objects.create(name="Jawwal Pay")
        cls.other_pm = PaymentMethod.objects.create(name="Bank of Palestine")
        cls.emp = User.objects.create_user("entry_recip_emp", password="x")
        UserProfile.objects.update_or_create(
            user=cls.emp,
            defaults={"role": UserProfile.Role.EMPLOYEE, "is_active_profile": True},
        )
        Customer.objects.create(name="Tester", created_by=cls.emp)

    def setUp(self):
        self.client.force_login(self.emp)

    def _post_sale(self, **extra):
        data = {
            "company": self.company.pk,
            "product": self.product.pk,
            "reference_number": "0501234567",
            "payer_name": "Tester",
            "sell_price_actual": "10",
            "payment_method": self.pm.pk,
        }
        data.update(extra)
        return self.client.post(reverse("sales:employee_entry"), data)

    def _two_recipients(self):
        a = PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد", sort_order=0)
        b = PaymentRecipient.objects.create(payment_method=self.pm, name="رامز", sort_order=1)
        return a, b

    def test_single_recipient_auto_assigned_on_save(self):
        only = PaymentRecipient.objects.create(payment_method=self.pm, name="أحمد")

        response = self._post_sale()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.get().payment_recipient, only)

    def test_two_recipients_without_choice_shows_error(self):
        self._two_recipients()

        response = self._post_sale()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertContains(response, "Pick who received the payment.")

    def test_two_recipients_with_choice_saved(self):
        _, b = self._two_recipients()

        response = self._post_sale(payment_recipient=b.pk)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.get().payment_recipient, b)

    def test_post_with_foreign_recipient_is_rejected(self):
        self._two_recipients()
        foreign = PaymentRecipient.objects.create(payment_method=self.other_pm, name="رائد")

        response = self._post_sale(payment_recipient=foreign.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertContains(response, "Selected recipient does not belong to this payment method.")

    def test_on_account_ignores_posted_recipient(self):
        a, _ = self._two_recipients()

        response = self._post_sale(on_account="1", payment_method="", payment_recipient=a.pk)

        self.assertEqual(response.status_code, 302)
        sale = Sale.objects.get()
        self.assertTrue(sale.on_account)
        self.assertIsNone(sale.payment_recipient_id)

    def test_tiles_carry_recipient_data(self):
        self._two_recipients()

        response = self.client.get(reverse("sales:employee_entry"))

        self.assertContains(response, "data-recipients=")
        self.assertContains(response, "أحمد")
        self.assertContains(response, 'id="payment-recipient-picker"')
        self.assertContains(response, 'id="id_payment_recipient"')

    def test_create_sale_service_rejects_missing_choice(self):
        self._two_recipients()

        with self.assertRaisesMessage(ValueError, "Pick who received the payment."):
            create_sale(
                company=self.company,
                product=self.product,
                reference_number="0501234567",
                payer_name="Tester",
                payment_method=self.pm,
                sell_price_actual=Decimal("10"),
                notes="",
                user=self.emp,
            )
        self.assertEqual(Sale.objects.count(), 0)


class SaleEditRecipientTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from customers.models import Customer

        cls.mgr = User.objects.create_user("edit_recip_mgr", password="x")
        UserProfile.objects.update_or_create(
            user=cls.mgr,
            defaults={"role": UserProfile.Role.MANAGEMENT, "is_active_profile": True},
        )
        cls.emp = User.objects.create_user("edit_recip_emp", password="x")
        UserProfile.objects.update_or_create(
            user=cls.emp,
            defaults={"role": UserProfile.Role.EMPLOYEE, "is_active_profile": True},
        )
        cls.company = Company.objects.create(
            name="EditRecipCo",
            opening_balance=Decimal("1000"),
            current_balance=Decimal("1000"),
        )
        cls.line = ProductLine.objects.create(company=cls.company, name="L")
        cls.product = Product.objects.create(
            line=cls.line,
            variant_label="P",
            cost_price=Decimal("5"),
            default_sell_price=Decimal("20"),
        )
        cls.pm = PaymentMethod.objects.create(name="Jawwal Pay")
        cls.other_pm = PaymentMethod.objects.create(name="Bank of Palestine")
        cls.a = PaymentRecipient.objects.create(payment_method=cls.pm, name="أحمد", sort_order=0)
        cls.b = PaymentRecipient.objects.create(payment_method=cls.pm, name="رامز", sort_order=1)
        cls.customer = Customer.objects.create(name="Edit Tester", created_by=cls.mgr)

    def _sale(self, *, user=None, on_account=False, recipient=None):
        return create_sale(
            company=self.company,
            product=self.product,
            reference_number="0501234567",
            payer_name="Ali",
            payment_method=None if on_account else self.pm,
            sell_price_actual=Decimal("20"),
            notes="",
            user=user or self.mgr,
            on_account=on_account,
            customer=self.customer if on_account else None,
            payment_recipient=None if on_account else (recipient or self.a),
        )

    @staticmethod
    def _edit_data(**extra):
        data = {
            "payer_name": "Ali",
            "reference_number": "0501234567",
            "sell_price_actual": "20",
            "notes": "",
        }
        data.update(extra)
        return data

    def _post_management_edit(self, sale, **extra):
        self.client.force_login(self.mgr)
        return self.client.post(
            reverse("sales:sale_edit", args=[sale.pk]), self._edit_data(**extra)
        )

    def test_edit_sets_recipient(self):
        sale = self._sale()

        response = self._post_management_edit(
            sale, payment_method=self.pm.pk, payment_recipient=self.b.pk
        )

        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.payment_recipient, self.b)

    def test_edit_switch_method_auto_assigns_single_recipient(self):
        only = PaymentRecipient.objects.create(payment_method=self.other_pm, name="رائد")
        sale = self._sale()

        response = self._post_management_edit(
            sale, payment_method=self.other_pm.pk, payment_recipient=""
        )

        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.payment_method, self.other_pm)
        self.assertEqual(sale.payment_recipient, only)

    def test_edit_switch_method_rejects_stale_recipient(self):
        PaymentRecipient.objects.create(payment_method=self.other_pm, name="رائد")
        sale = self._sale()

        response = self._post_management_edit(
            sale, payment_method=self.other_pm.pk, payment_recipient=self.a.pk
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selected recipient does not belong to this payment method.")
        sale.refresh_from_db()
        self.assertEqual(sale.payment_method, self.pm)
        self.assertEqual(sale.payment_recipient, self.a)

    def test_edit_switch_to_method_without_recipients_clears_recipient(self):
        sale = self._sale()

        response = self._post_management_edit(
            sale, payment_method=self.other_pm.pk, payment_recipient=""
        )

        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.payment_method, self.other_pm)
        self.assertIsNone(sale.payment_recipient_id)

    def test_edit_many_recipients_without_choice_shows_error(self):
        sale = self._sale()

        response = self._post_management_edit(
            sale, payment_method=self.pm.pk, payment_recipient=""
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pick who received the payment.")
        sale.refresh_from_db()
        self.assertEqual(sale.payment_recipient, self.a)

    def test_edit_keeps_current_recipient_after_it_was_deactivated(self):
        sale = self._sale()
        PaymentRecipient.objects.filter(pk=self.a.pk).update(is_active=False)

        response = self._post_management_edit(
            sale, payment_method=self.pm.pk, payment_recipient=self.a.pk, payer_name="Omar"
        )

        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.payer_name, "Omar")
        self.assertEqual(sale.payment_recipient, self.a)

    def test_edit_on_account_sale_keeps_recipient_none(self):
        sale = self._sale(on_account=True)

        response = self._post_management_edit(
            sale, payment_method=self.pm.pk, payment_recipient=self.a.pk
        )

        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertIsNone(sale.payment_method_id)
        self.assertIsNone(sale.payment_recipient_id)

    def test_employee_edit_on_account_sale_ignores_posted_recipient(self):
        sale = self._sale(user=self.emp, on_account=True)
        self.client.force_login(self.emp)

        response = self.client.post(
            reverse("sales:employee_sale_edit", args=[sale.pk]),
            self._edit_data(payment_method=self.pm.pk, payment_recipient=self.a.pk),
        )

        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertIsNone(sale.payment_method_id)
        self.assertIsNone(sale.payment_recipient_id)

    def test_employee_edit_sets_recipient(self):
        sale = self._sale(user=self.emp)
        self.client.force_login(self.emp)

        response = self.client.post(
            reverse("sales:employee_sale_edit", args=[sale.pk]),
            self._edit_data(payment_method=self.pm.pk, payment_recipient=self.b.pk),
        )

        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.payment_recipient, self.b)

    def test_update_service_records_audit_change(self):
        from audit.models import AuditAction, AuditLog

        sale = self._sale()

        update_sale_fields(
            sale=sale,
            payment_method=self.pm,
            payer_name="Ali",
            reference_number="0501234567",
            sell_price_actual=Decimal("20"),
            notes="",
            user=self.mgr,
            payment_recipient=self.b,
        )

        row = AuditLog.objects.filter(
            action=AuditAction.UPDATE, object_id=str(sale.pk)
        ).get()
        self.assertIn("payment_recipient_id", row.changes)
        self.assertEqual(row.changes["payment_recipient_id"]["new"], self.b.pk)

    def test_update_service_on_account_sale_clears_recipient(self):
        sale = self._sale(on_account=True)

        updated = update_sale_fields(
            sale=sale,
            payment_method=self.pm,
            payer_name="Ali",
            reference_number="0501234567",
            sell_price_actual=Decimal("20"),
            notes="",
            user=self.mgr,
            payment_recipient=self.a,
        )

        self.assertIsNone(updated.payment_method_id)
        self.assertIsNone(updated.payment_recipient_id)

    def test_edit_pages_render_filterable_recipient_select(self):
        sale = self._sale(user=self.emp)
        urls = [
            (self.mgr, reverse("sales:sale_edit", args=[sale.pk])),
            (self.emp, reverse("sales:employee_sale_edit", args=[sale.pk])),
        ]
        for user, url in urls:
            with self.subTest(url=url):
                self.client.force_login(user)

                response = self.client.get(url)

                self.assertContains(response, 'data-recipient-for="id_payment_method"')
                self.assertContains(response, f'data-method="{self.pm.pk}"')
                self.assertContains(response, "Jawwal Pay — أحمد")
                self.assertContains(response, "js/recipient-select-filter.js")


class PendingPaymentsRecipientTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mgr = User.objects.create_user("pending_recip_mgr", password="x")
        UserProfile.objects.update_or_create(
            user=cls.mgr,
            defaults={"role": UserProfile.Role.MANAGEMENT, "is_active_profile": True},
        )
        cls.company = Company.objects.create(
            name="PendingRecipCo",
            opening_balance=Decimal("1000"),
            current_balance=Decimal("1000"),
        )
        cls.line = ProductLine.objects.create(company=cls.company, name="L")
        cls.product = Product.objects.create(
            line=cls.line,
            variant_label="P",
            cost_price=Decimal("5"),
            default_sell_price=Decimal("20"),
        )
        cls.pm = PaymentMethod.objects.create(name="Jawwal Pay")
        cls.a = PaymentRecipient.objects.create(payment_method=cls.pm, name="أحمد", sort_order=0)
        cls.b = PaymentRecipient.objects.create(payment_method=cls.pm, name="رامز", sort_order=1)

    def setUp(self):
        self.client.force_login(self.mgr)

    def _pending_sale(self, recipient):
        return create_sale(
            company=self.company,
            product=self.product,
            reference_number="0501234567",
            payer_name="Ali",
            payment_method=self.pm,
            sell_price_actual=Decimal("20"),
            notes="",
            user=self.mgr,
            payment_recipient=recipient,
        )

    def test_pending_page_shows_chosen_recipient(self):
        self._pending_sale(self.b)

        response = self.client.get(reverse("sales:pending_payments"))

        self.assertContains(response, "رامز")
        self.assertNotContains(response, "أحمد")

    def test_pending_page_flags_missing_recipient_on_multi_recipient_method(self):
        sale = self._pending_sale(self.a)
        Sale.objects.filter(pk=sale.pk).update(payment_recipient=None)

        response = self.client.get(reverse("sales:pending_payments"))

        self.assertContains(response, "No recipient")
        self.assertContains(response, reverse("sales:sale_edit", args=[sale.pk]))


class RecipientFormErrorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.emp = User.objects.create_user("form_recip_emp", password="x")
        cls.company = Company.objects.create(
            name="FormRecipCo",
            opening_balance=Decimal("1000"),
            current_balance=Decimal("1000"),
        )
        cls.line = ProductLine.objects.create(company=cls.company, name="L")
        cls.product = Product.objects.create(
            line=cls.line,
            variant_label="P",
            cost_price=Decimal("5"),
            default_sell_price=Decimal("10"),
        )
        cls.pm = PaymentMethod.objects.create(name="Jawwal Pay")
        cls.a = PaymentRecipient.objects.create(payment_method=cls.pm, name="أحمد")
        cls.b = PaymentRecipient.objects.create(payment_method=cls.pm, name="رامز")
        cls.stale = PaymentRecipient.objects.create(
            payment_method=cls.pm, name="رائد", is_active=False
        )

    def _sale_form(self, **extra):
        from sales.forms import EmployeeSaleForm

        data = {
            "company": self.company.pk,
            "product": self.product.pk,
            "reference_number": "0501234567",
            "payer_name": "Tester",
            "sell_price_actual": "10",
            "payment_method": self.pm.pk,
        }
        data.update(extra)
        return EmployeeSaleForm(data=data, user=self.emp, company_id=self.company.pk)

    def test_invalid_recipient_id_reports_single_error(self):
        form = self._sale_form(payment_recipient="999999")

        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors["payment_recipient"]), 1, form.errors)

    def test_on_account_with_stale_recipient_is_valid(self):
        form = self._sale_form(
            on_account="1", payment_method="", payment_recipient=str(self.stale.pk)
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["payment_recipient"])

    def test_paid_via_employee_with_stale_recipient_is_valid(self):
        from core.models import AppSettings
        from employees.models import EmployeeProfile

        AppSettings.objects.update_or_create(
            pk=1, defaults={"sales_show_employee_payment": True}
        )
        EmployeeProfile.objects.create(user=self.emp, monthly_salary=Decimal("0"))
        self.emp.refresh_from_db()

        form = self._sale_form(
            paid_via_employee="1", payment_method="", payment_recipient=str(self.stale.pk)
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["payment_recipient"])

    def test_edit_form_invalid_recipient_id_reports_single_error(self):
        from sales.forms import ManagementSaleEditForm

        sale = create_sale(
            company=self.company,
            product=self.product,
            reference_number="0501234567",
            payer_name="Ali",
            payment_method=self.pm,
            sell_price_actual=Decimal("10"),
            notes="",
            user=self.emp,
            payment_recipient=self.a,
        )
        form = ManagementSaleEditForm(
            data={
                "payment_method": self.pm.pk,
                "payment_recipient": "999999",
                "payer_name": "Ali",
                "reference_number": "0501234567",
                "sell_price_actual": "10",
                "notes": "",
            },
            instance=sale,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors["payment_recipient"]), 1, form.errors)
