import json

from django.utils.translation import gettext_lazy as _

from sales.models import PaymentMethod, PaymentRecipient


def resolve_payment_recipient(
    payment_method: PaymentMethod | None, chosen: PaymentRecipient | None
) -> PaymentRecipient | None:
    """Return the recipient to record for a payment through ``payment_method``.

    A single active recipient is auto-assigned; with two or more, ``chosen`` is
    required. Raises ``ValueError`` when the choice is missing or invalid.
    """
    active = list(payment_method.active_recipients()) if payment_method else []

    if chosen is not None:
        if chosen.pk not in {r.pk for r in active}:
            raise ValueError(_("Selected recipient does not belong to this payment method."))
        return chosen

    if not active:
        return None
    if len(active) == 1:
        return active[0]
    raise ValueError(_("Pick who received the payment."))


def resolve_edited_payment_recipient(
    sale, payment_method: PaymentMethod | None, chosen: PaymentRecipient | None
) -> PaymentRecipient | None:
    """``resolve_payment_recipient`` for an edit of ``sale``.

    The sale's current recipient stays valid while the method is unchanged,
    even if that recipient has since been deactivated.
    """
    if (
        chosen is not None
        and payment_method is not None
        and chosen.pk == sale.payment_recipient_id
        and payment_method.pk == sale.payment_method_id
        and chosen.payment_method_id == payment_method.pk
    ):
        return chosen
    return resolve_payment_recipient(payment_method, chosen)


def resolve_legacy_payment_recipient(payment_method: PaymentMethod) -> PaymentRecipient | None:
    """Recipient for money recorded without one (e.g. before the method had recipients).

    Never raises: the single active recipient when there is exactly one, else ``None``.
    """
    active = list(payment_method.active_recipients())
    return active[0] if len(active) == 1 else None


def recipients_json(payment_method: PaymentMethod) -> str:
    return json.dumps(
        [{"id": r.pk, "name": r.name} for r in payment_method.active_recipients()],
        ensure_ascii=False,
    )
