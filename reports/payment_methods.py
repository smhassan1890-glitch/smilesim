"""Payment-methods report: money actually received on one payment method.

Rows are money movements, not sales: direct (non on-account) sales and
customer payments. On-account sales settled by a payment are attached to that
payment row as ``settled_sales`` for display and never summed on their own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Union

from django.db.models import Prefetch

from customers.models import CustomerPayment
from sales.models import PaymentMethod, PaymentRecipient, Sale

RecipientFilter = Union[Literal["all", "none"], PaymentRecipient]
Kind = Literal["all", "sales", "settlements"]


@dataclass
class ReportRow:
    kind: Literal["sale", "payment"]
    pk: int
    created_at: datetime
    name: str
    reference: str
    company_product: str
    recipient_name: str
    employee: str
    amount: Decimal
    is_pending: bool
    settled_sales: list[Sale] = field(default_factory=list)


@dataclass
class RecipientTotal:
    recipient_name: str
    total: Decimal
    count: int


@dataclass
class PaymentMethodReport:
    rows: list[ReportRow]
    total: Decimal
    count: int
    sales_total: Decimal
    settlements_total: Decimal
    pending_total: Decimal
    by_recipient: list[RecipientTotal]


def _filter_recipient(qs, recipient: RecipientFilter):
    if recipient == "all":
        return qs
    if recipient == "none":
        return qs.filter(payment_recipient__isnull=True)
    return qs.filter(payment_recipient=recipient)


def _sale_row(sale: Sale) -> ReportRow:
    return ReportRow(
        kind="sale",
        pk=sale.pk,
        created_at=sale.created_at,
        name=sale.payer_name,
        reference=sale.reference_number,
        company_product=f"{sale.company.name} · {sale.product.display_name}",
        recipient_name=sale.payment_recipient.name if sale.payment_recipient else "",
        employee=sale.created_by.username,
        amount=sale.sell_price_actual,
        is_pending=sale.status == Sale.Status.PENDING,
    )


def _payment_row(payment: CustomerPayment) -> ReportRow:
    return ReportRow(
        kind="payment",
        pk=payment.pk,
        created_at=payment.created_at,
        name=payment.customer.name,
        reference="",
        company_product="",
        recipient_name=payment.payment_recipient.name if payment.payment_recipient else "",
        employee=payment.created_by.username,
        amount=payment.amount,
        is_pending=False,
        settled_sales=list(payment.settled_sales.all()),
    )


def _by_recipient(sales: list[Sale], payments: list[CustomerPayment]) -> list[RecipientTotal]:
    buckets: dict[int | None, list] = {}
    for obj in [*sales, *payments]:
        r = obj.payment_recipient
        key = r.pk if r else None
        if key not in buckets:
            sort_key = (0, r.sort_order, r.name) if r else (1, 0, "")
            buckets[key] = [sort_key, r.name if r else "", Decimal("0"), 0]
        bucket = buckets[key]
        bucket[2] += obj.sell_price_actual if isinstance(obj, Sale) else obj.amount
        bucket[3] += 1
    return [
        RecipientTotal(recipient_name=name, total=total, count=count)
        for _, name, total, count in sorted(buckets.values(), key=lambda b: b[0])
    ]


def build_payment_method_report(
    *,
    payment_method: PaymentMethod,
    recipient: RecipientFilter,
    date_from: date,
    date_to: date,
    kind: Kind,
) -> PaymentMethodReport:
    date_range = (date_from, date_to)

    sales: list[Sale] = []
    if kind in ("all", "sales"):
        sales_qs = (
            Sale.objects.filter(
                payment_method=payment_method,
                on_account=False,
                created_at__date__range=date_range,
            )
            .exclude(status=Sale.Status.CANCELLED)
            .select_related("company", "product__line", "created_by", "payment_recipient")
        )
        sales = list(_filter_recipient(sales_qs, recipient))

    payments: list[CustomerPayment] = []
    if kind in ("all", "settlements"):
        payments_qs = (
            CustomerPayment.objects.filter(
                payment_method=payment_method,
                created_at__date__range=date_range,
            )
            .select_related("customer", "created_by", "payment_recipient")
            .prefetch_related(
                Prefetch(
                    "settled_sales",
                    queryset=Sale.objects.exclude(status=Sale.Status.CANCELLED)
                    .select_related("company", "product__line")
                    .order_by("created_at", "pk"),
                )
            )
        )
        payments = list(_filter_recipient(payments_qs, recipient))

    rows = [_sale_row(s) for s in sales] + [_payment_row(p) for p in payments]
    rows.sort(key=lambda r: (r.created_at, r.kind == "payment", r.pk))

    sales_total = sum((s.sell_price_actual for s in sales), Decimal("0"))
    settlements_total = sum((p.amount for p in payments), Decimal("0"))
    pending_total = sum(
        (s.sell_price_actual for s in sales if s.status == Sale.Status.PENDING), Decimal("0")
    )

    return PaymentMethodReport(
        rows=rows,
        total=sales_total + settlements_total,
        count=len(rows),
        sales_total=sales_total,
        settlements_total=settlements_total,
        pending_total=pending_total,
        by_recipient=_by_recipient(sales, payments) if recipient == "all" else [],
    )
