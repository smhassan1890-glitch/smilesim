"""CRUD views for the PaymentMethod taxonomy (management-only)."""

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch, ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from accounts.permissions import management_required
from core.pagination import paginate_request
from sales.forms import PaymentMethodForm, PaymentRecipientFormSet
from sales.models import PaymentMethod, PaymentRecipient


@management_required
def payment_method_list(request):
    qs = PaymentMethod.objects.order_by("name").prefetch_related(
        Prefetch(
            "recipients",
            queryset=PaymentRecipient.objects.filter(is_active=True),
            to_attr="active_recipient_list",
        )
    )
    page_obj = paginate_request(request, qs)
    return render(
        request,
        "sales/payment_method_list.html",
        {"page_obj": page_obj, "title": _("Payment methods")},
    )


def _save_method_and_recipients(request, form, formset):
    with transaction.atomic():
        method = form.save()
        formset.instance = method
        recipients = formset.save(commit=False)
        for recipient in formset.deleted_objects:
            try:
                with transaction.atomic():
                    recipient.delete()
            except ProtectedError:
                messages.warning(
                    request,
                    _(
                        "“%(name)s” is used by existing records and was not "
                        "deleted. Deactivate it instead."
                    )
                    % {"name": recipient.name},
                )
        for recipient in recipients:
            recipient.save()
    return method


@management_required
def payment_method_create(request):
    form = PaymentMethodForm(request.POST or None, request.FILES or None)
    formset = PaymentRecipientFormSet(request.POST or None, prefix="recipients")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        _save_method_and_recipients(request, form, formset)
        messages.success(request, _("Payment method saved."))
        return redirect("sales:payment_method_list")
    return render(
        request,
        "sales/payment_method_form.html",
        {"form": form, "formset": formset, "title": _("New payment method")},
    )


@management_required
def payment_method_edit(request, pk):
    obj = get_object_or_404(PaymentMethod, pk=pk)
    form = PaymentMethodForm(request.POST or None, request.FILES or None, instance=obj)
    formset = PaymentRecipientFormSet(
        request.POST or None, instance=obj, prefix="recipients"
    )
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        _save_method_and_recipients(request, form, formset)
        messages.success(request, _("Payment method updated."))
        return redirect("sales:payment_method_list")
    return render(
        request,
        "sales/payment_method_form.html",
        {
            "form": form,
            "formset": formset,
            "title": _("Edit payment method"),
            "method": obj,
        },
    )


@management_required
@transaction.atomic
def payment_method_delete(request, pk):
    obj = get_object_or_404(PaymentMethod, pk=pk)
    if request.method != "POST":
        return redirect("sales:payment_method_list")

    name = obj.name
    try:
        obj.delete()
    except ProtectedError:
        # ``Sale`` and ``Payment`` both reference PaymentMethod with
        # on_delete=PROTECT — refuse the delete with a clear message
        # instead of leaking a 500 to the admin.
        messages.error(
            request,
            _(
                "Cannot delete “%(name)s” because existing sales or customer "
                "payments still reference it. Mark it inactive instead, or "
                "first move those records to another method."
            )
            % {"name": name},
        )
        return redirect("sales:payment_method_list")

    messages.success(
        request, _("Payment method “%(name)s” was deleted.") % {"name": name}
    )
    return redirect("sales:payment_method_list")
