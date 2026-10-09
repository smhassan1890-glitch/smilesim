"""Tests for the payment-methods report: query module and report page."""

import csv
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext

from accounts.models import UserProfile
from customers.services import approve_sale, create_customer, record_customer_payment
from reports.payment_methods import build_payment_method_report
from reports.tests import _ReportsBase
from sales.models import PaymentMethod, PaymentRecipient, Sale
from sales.services import create_sale, mark_sale_paid


def _d(v):
    return Decimal(str(v))


class _PaymentReportFixtures:
    """Fixture helpers shared by the report query and view tests (mix into ``_ReportsBase``)."""

    def _recipient(self, name, sort_order=0):
        return PaymentRecipient.objects.create(
            payment_method=self.cash, name=name, sort_order=sort_order
        )

    def _direct_sale(self, *, sell, recipient=None, paid=True, pm=None):
        s = create_sale(
            company=self.company,
            product=self.product,
            reference_number=f"R-{Sale.objects.count() + 1}",
            payer_name="Ali",
            payment_method=pm or self.cash,
            sell_price_actual=_d(sell),
            notes="",
            user=self.user,
            payment_recipient=recipient,
        )
        if paid:
            s = mark_sale_paid(sale=s, user=self.user)
        return s

    def _settled_on_account(self, *, sell, pay, recipient=None, name="Cust", pm=None):
        customer = create_customer(name=name, phones=[], user=self.user)
        sale = self._make_sale(sell=sell, on_account=True, customer=customer)
        approve_sale(sale=sale, user=self.user)
        payment = record_customer_payment(
            customer=customer,
            amount=_d(pay),
            payment_method=pm or self.cash,
            payment_recipient=recipient,
            user=self.user,
        )
        return sale, payment

    def _set_created_at(self, obj, dt):
        type(obj).objects.filter(pk=obj.pk).update(created_at=dt)


class PaymentMethodReportTests(_PaymentReportFixtures, _ReportsBase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()

    def _report(self, *, recipient="all", kind="all", date_from=None, date_to=None, pm=None):
        return build_payment_method_report(
            payment_method=pm or self.cash,
            recipient=recipient,
            date_from=date_from or self.today,
            date_to=date_to or self.today,
            kind=kind,
        )

    def test_direct_sale_counted(self):
        sale = self._make_sale(sell=25, paid=True)
        report = self._report()
        self.assertEqual(report.total, _d(25))
        self.assertEqual(report.count, 1)
        self.assertEqual(report.sales_total, _d(25))
        self.assertEqual(report.settlements_total, _d(0))
        row = report.rows[0]
        self.assertEqual(row.kind, "sale")
        self.assertEqual(row.pk, sale.pk)
        self.assertEqual(row.name, "Ali")
        self.assertEqual(row.reference, sale.reference_number)
        self.assertEqual(row.company_product, f"ReportCo · {self.product.display_name}")
        self.assertEqual(row.recipient_name, "")
        self.assertEqual(row.employee, self.user.username)
        self.assertEqual(row.amount, _d(25))
        self.assertFalse(row.is_pending)
        self.assertEqual(row.settled_sales, [])

    def test_cancelled_sale_excluded(self):
        self._make_sale(sell=20, paid=True)
        cancelled = self._make_sale(sell=30)
        Sale.objects.filter(pk=cancelled.pk).update(status=Sale.Status.CANCELLED)
        report = self._report()
        self.assertEqual(report.total, _d(20))
        self.assertEqual(report.count, 1)

    def test_settled_on_account_sale_counted_once(self):
        sale, payment = self._settled_on_account(sell=50, pay=50)
        sale.refresh_from_db()
        self.assertEqual(sale.payment_method_id, self.cash.pk)
        report = self._report()
        self.assertEqual(report.total, _d(50))
        self.assertEqual(report.count, 1)
        self.assertEqual(report.sales_total, _d(0))
        self.assertEqual(report.settlements_total, _d(50))
        self.assertEqual(len(report.rows), 1)
        row = report.rows[0]
        self.assertEqual(row.kind, "payment")
        self.assertEqual(row.pk, payment.pk)
        self.assertEqual(row.name, "Cust")
        self.assertEqual(row.reference, "")
        self.assertEqual(row.company_product, "")
        self.assertFalse(row.is_pending)
        self.assertEqual(row.settled_sales, [sale])

    def test_recipient_filter_specific_and_none(self):
        # Recorded before the method had recipients, so they have none.
        s_none = self._direct_sale(sell=10)
        _, p_none = self._settled_on_account(sell=5, pay=5, name="NoRecip")
        ahmad = self._recipient("Ahmad")
        raed = self._recipient("Raed")
        s_ahmad = self._direct_sale(sell=30, recipient=ahmad)
        self._direct_sale(sell=20, recipient=raed)
        _, p_ahmad = self._settled_on_account(sell=15, pay=15, recipient=ahmad)

        report = self._report(recipient=ahmad)
        self.assertEqual(report.total, _d(45))
        self.assertEqual(
            {(r.kind, r.pk) for r in report.rows},
            {("sale", s_ahmad.pk), ("payment", p_ahmad.pk)},
        )
        self.assertTrue(all(r.recipient_name == "Ahmad" for r in report.rows))
        self.assertEqual(report.by_recipient, [])

        report = self._report(recipient="none")
        self.assertEqual(report.total, _d(15))
        self.assertEqual(report.sales_total, _d(10))
        self.assertEqual(report.settlements_total, _d(5))
        self.assertEqual(
            {(r.kind, r.pk) for r in report.rows},
            {("sale", s_none.pk), ("payment", p_none.pk)},
        )
        self.assertTrue(all(r.recipient_name == "" for r in report.rows))
        self.assertEqual(report.by_recipient, [])

    def test_other_method_excluded(self):
        other = PaymentMethod.objects.create(name="Bank")
        self._direct_sale(sell=70, pm=other)
        self._settled_on_account(sell=80, pay=80, pm=other, name="OtherCust")
        own = self._make_sale(sell=20, paid=True)

        report = self._report()
        self.assertEqual([(r.kind, r.pk) for r in report.rows], [("sale", own.pk)])
        self.assertEqual(report.total, _d(20))
        self.assertEqual(report.count, 1)
        self.assertEqual(report.sales_total, _d(20))
        self.assertEqual(report.settlements_total, _d(0))
        self.assertEqual(
            [(b.recipient_name, b.total, b.count) for b in report.by_recipient],
            [("", _d(20), 1)],
        )

        other_report = self._report(pm=other)
        self.assertEqual(other_report.total, _d(150))

    def test_kind_filter_sales_only(self):
        direct = self._make_sale(sell=20, paid=True)
        _, payment = self._settled_on_account(sell=40, pay=40)

        report = self._report(kind="sales")
        self.assertEqual([(r.kind, r.pk) for r in report.rows], [("sale", direct.pk)])
        self.assertEqual(report.total, _d(20))
        self.assertEqual(report.settlements_total, _d(0))

        report = self._report(kind="settlements")
        self.assertEqual([(r.kind, r.pk) for r in report.rows], [("payment", payment.pk)])
        self.assertEqual(report.total, _d(40))
        self.assertEqual(report.sales_total, _d(0))

    def test_pending_total(self):
        self._make_sale(sell=20, paid=True)
        pending = self._make_sale(sell=35)
        report = self._report()
        self.assertEqual(report.total, _d(55))
        self.assertEqual(report.pending_total, _d(35))
        rows = {r.pk: r for r in report.rows}
        self.assertTrue(rows[pending.pk].is_pending)

    def test_by_recipient_breakdown(self):
        self._direct_sale(sell=10)
        # Alphabetically أحمد < رائد, so a lower sort_order on رائد proves sort_order wins.
        ahmad = self._recipient("أحمد", sort_order=2)
        raed = self._recipient("رائد", sort_order=1)
        self._direct_sale(sell=20, recipient=ahmad)
        self._settled_on_account(sell=10, pay=10, recipient=ahmad)
        self._direct_sale(sell=20, recipient=raed)

        report = self._report()
        self.assertEqual(
            [(b.recipient_name, b.total, b.count) for b in report.by_recipient],
            [("رائد", _d(20), 1), ("أحمد", _d(30), 2), ("", _d(10), 1)],
        )

    def test_rows_sorted_ascending(self):
        base = timezone.make_aware(datetime.combine(self.today, time(9, 0)))
        s_late = self._make_sale(sell=20, paid=True)
        s_early = self._make_sale(sell=20, paid=True)
        _, payment = self._settled_on_account(sell=20, pay=20)
        self._set_created_at(s_late, base + timedelta(hours=3))
        self._set_created_at(s_early, base)
        self._set_created_at(payment, base + timedelta(hours=1))

        report = self._report()
        self.assertEqual(
            [(r.kind, r.pk) for r in report.rows],
            [("sale", s_early.pk), ("payment", payment.pk), ("sale", s_late.pk)],
        )
        created = [r.created_at for r in report.rows]
        self.assertEqual(created, sorted(created))

    def test_date_to_is_inclusive_local_day(self):
        date_to = date(2026, 3, 10)
        inside = self._make_sale(sell=20, paid=True)
        outside = self._make_sale(sell=30, paid=True)
        self._set_created_at(inside, timezone.make_aware(datetime.combine(date_to, time(23, 30))))
        self._set_created_at(
            outside,
            timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time(0, 10))),
        )

        report = self._report(date_from=date(2026, 3, 1), date_to=date_to)
        self.assertEqual([r.pk for r in report.rows], [inside.pk])
        self.assertEqual(report.total, _d(20))

    def test_date_from_is_inclusive_local_day(self):
        date_from = date(2026, 3, 1)
        before = self._make_sale(sell=30, paid=True)
        inside = self._make_sale(sell=20, paid=True)
        self._set_created_at(
            before,
            timezone.make_aware(datetime.combine(date_from - timedelta(days=1), time(23, 50))),
        )
        self._set_created_at(inside, timezone.make_aware(datetime.combine(date_from, time(0, 10))))

        report = self._report(date_from=date_from, date_to=date(2026, 3, 10))
        self.assertEqual([r.pk for r in report.rows], [inside.pk])
        self.assertEqual(report.total, _d(20))

    def test_cancelled_sale_hidden_from_settled_sales(self):
        customer = create_customer(name="Cust", phones=[], user=self.user)
        kept = self._make_sale(sell=20, on_account=True, customer=customer)
        cancelled = self._make_sale(sell=30, on_account=True, customer=customer)
        approve_sale(sale=kept, user=self.user)
        approve_sale(sale=cancelled, user=self.user)
        payment = record_customer_payment(
            customer=customer, amount=_d(50), payment_method=self.cash, user=self.user
        )
        self.assertEqual(
            set(payment.settled_sales.values_list("pk", flat=True)), {kept.pk, cancelled.pk}
        )
        # cancel_sale leaves customer_payment set on the cancelled sale.
        Sale.objects.filter(pk=cancelled.pk).update(status=Sale.Status.CANCELLED)

        report = self._report()
        self.assertEqual(len(report.rows), 1)
        self.assertEqual(report.rows[0].settled_sales, [kept])
        self.assertEqual(report.total, _d(50))

    def test_query_count_bounded(self):
        for _ in range(3):
            self._make_sale(sell=20, paid=True)
        for i in range(2):
            self._settled_on_account(sell=20, pay=20, name=f"C{i}")
        with self.assertNumQueries(3):
            report = self._report()
            for r in report.rows:
                for s in r.settled_sales:
                    str(s.company)
                    s.product.display_name
        self.assertEqual(report.count, 5)


class PaymentMethodsReportViewTests(_PaymentReportFixtures, _ReportsBase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.url = reverse("reports:payment_methods_report")

    def _csv_rows(self, response):
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertTrue(body.startswith("\ufeff"))
        return list(csv.reader(io.StringIO(body[1:])))

    def test_page_without_method_shows_prompt(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "reports/payment_methods_report.html")
        self.assertContains(r, "Choose a payment method")
        self.assertIsNone(r.context["report"])
        self.assertNotContains(r, "<table")

    def test_default_period_is_month_to_date(self):
        r = self.client.get(self.url)
        form = r.context["form"]
        self.assertEqual(form.cleaned_data["date_from"], self.today.replace(day=1))
        self.assertEqual(form.cleaned_data["date_to"], self.today)

    def test_results_partial_on_htmx(self):
        r = self.client.get(self.url, {"payment_method": self.cash.pk}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "reports/partials/payment_methods_report_results.html")
        self.assertTemplateNotUsed(r, "reports/payment_methods_report.html")

    def test_totals_rendered(self):
        ahmad = self._recipient("Ahmad")
        self._direct_sale(sell=30, recipient=ahmad)
        self._direct_sale(sell=12, recipient=ahmad, paid=False)
        self._settled_on_account(sell=55, pay=55, recipient=ahmad)

        r = self.client.get(self.url, {"payment_method": self.cash.pk})

        report = r.context["report"]
        self.assertEqual(report.total, _d(97))
        self.assertEqual(report.count, 3)
        self.assertContains(r, intcomma(_d("97.00")))
        self.assertContains(r, intcomma(_d("42.00")))
        self.assertContains(r, intcomma(_d("55.00")))
        self.assertContains(r, intcomma(_d("12.00")))
        self.assertContains(r, "Ahmad")

    def test_recipient_filter_applied(self):
        ahmad = self._recipient("Ahmad")
        raed = self._recipient("Raed")
        self._direct_sale(sell=30, recipient=ahmad)
        self._direct_sale(sell=20, recipient=raed)

        r = self.client.get(self.url, {"payment_method": self.cash.pk, "recipient": ahmad.pk})

        self.assertEqual(r.context["report"].total, _d(30))

    def test_recipient_of_other_method_rejected(self):
        bank = PaymentMethod.objects.create(name="Bank")
        foreign = PaymentRecipient.objects.create(payment_method=bank, name="Sami")

        r = self.client.get(self.url, {"payment_method": self.cash.pk, "recipient": foreign.pk})

        self.assertIsNone(r.context["report"])
        self.assertIn("recipient", r.context["form"].errors)

    def test_date_from_after_date_to_rejected(self):
        r = self.client.get(
            self.url,
            {
                "payment_method": self.cash.pk,
                "date_from": self.today.isoformat(),
                "date_to": (self.today - timedelta(days=1)).isoformat(),
            },
        )
        self.assertIsNone(r.context["report"])
        self.assertTrue(r.context["form"].errors)

    def test_rows_paginated_by_50(self):
        for _ in range(51):
            self._direct_sale(sell=10)

        r = self.client.get(self.url, {"payment_method": self.cash.pk})

        page_obj = r.context["page_obj"]
        self.assertEqual(len(page_obj.object_list), 50)
        self.assertEqual(page_obj.paginator.count, 51)

    def test_csv_export(self):
        ahmad = self._recipient("Ahmad")
        sale, _payment = self._settled_on_account(sell=50, pay=50, recipient=ahmad)
        self._direct_sale(sell=30, recipient=ahmad)

        r = self.client.get(self.url, {"payment_method": self.cash.pk, "export": "csv"})

        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/csv"))
        rows = self._csv_rows(r)
        self.assertIn(gettext("Recipient"), rows[0])
        self.assertEqual(len(rows), 3)
        payment_row = next(row for row in rows[1:] if row[1] == gettext("Settlement"))
        self.assertIn(f"#{sale.pk}", payment_row[-1])
        self.assertIn("Ahmad", payment_row)

    def test_csv_exports_all_rows_not_just_page(self):
        for _ in range(51):
            self._direct_sale(sell=10)

        r = self.client.get(self.url, {"payment_method": self.cash.pk, "export": "csv"})

        self.assertEqual(len(self._csv_rows(r)), 52)

    def test_query_count_does_not_grow_with_rows(self):
        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(self.url, {"payment_method": self.cash.pk})
            return len(ctx.captured_queries)

        count_queries()  # first request creates the AppSettings / SiteBranding singletons
        self._direct_sale(sell=10)
        self._settled_on_account(sell=20, pay=20, name="C0")
        baseline = count_queries()
        for i in range(3):
            self._direct_sale(sell=10)
            self._settled_on_account(sell=20, pay=20, name=f"C{i + 1}")
        self.assertEqual(count_queries(), baseline)

    def test_non_management_forbidden(self):
        employee = get_user_model().objects.create_user("emp_pm", password="x")
        UserProfile.objects.update_or_create(
            user=employee,
            defaults={"role": UserProfile.Role.EMPLOYEE, "is_active_profile": True},
        )
        self.client.force_login(employee)

        r = self.client.get(self.url, {"payment_method": self.cash.pk})

        self.assertRedirects(r, reverse("core:forbidden"), fetch_redirect_response=False)

    def test_nav_link_present(self):
        r = self.client.get(reverse("reports:dashboard"))
        self.assertContains(r, reverse("reports:payment_methods_report"))
