from django import forms
from django.utils.translation import gettext_lazy as _

from companies.models import Company, Product
from sales.models import PaymentMethod, PaymentRecipient


class StalePhoneThresholdDaysForm(forms.Form):
    stale_phone_threshold_days = forms.IntegerField(
        label=_("Days without a new sale entry"),
        min_value=1,
        max_value=3650,
    )


class StalePhoneLineEditForm(forms.Form):
    sim_identifier = forms.CharField(
        label=_("SIM / chip"),
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
    )


class StalePhonesFilterForm(forms.Form):
    """GET filters for the idle-lines report (subset of the management sales filter bar)."""

    q = forms.CharField(
        label=_("Search"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "id": "stale-filter-q",
                "class": "form-control form-control-sm",
                "placeholder": _("Reference, payer, company…"),
                "autocomplete": "off",
            }
        ),
    )
    company = forms.ModelChoiceField(
        label=_("Company"),
        queryset=Company.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    product = forms.ModelChoiceField(
        label=_("Product"),
        queryset=Product.objects.select_related("line").all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.select_related(
            "line", "line__company"
        ).order_by("line__company__name", "line__sort_order", "line__name", "variant_label")


class RecipientFilterSelect(forms.Select):
    """Recipient options carry ``data-method``; the "all" / "none" options stay method-agnostic."""

    method_by_value: dict = {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        method_id = self.method_by_value.get(str(value))
        if method_id is not None:
            option["attrs"]["data-method"] = str(method_id)
        return option


class PaymentMethodReportForm(forms.Form):
    """GET filters for the payment-methods report.

    Dates are required here; the view fills the month-to-date defaults when
    they are absent from the query string.
    """

    payment_method = forms.ModelChoiceField(
        label=_("Payment method"),
        queryset=PaymentMethod.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    recipient = forms.ChoiceField(
        label=_("Recipient"),
        required=False,
        widget=RecipientFilterSelect(
            attrs={"class": "form-select", "data-recipient-for": "id_payment_method"}
        ),
    )
    date_from = forms.DateField(
        label=_("Date from"),
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    date_to = forms.DateField(
        label=_("Date to"),
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    kind = forms.ChoiceField(
        label=_("Type"),
        choices=[
            ("all", _("All")),
            ("sales", _("Sales")),
            ("settlements", _("Settlements")),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        recipients = list(
            PaymentRecipient.objects.order_by("payment_method__name", "sort_order", "name")
        )
        self._recipients = {str(r.pk): r for r in recipients}
        field = self.fields["recipient"]
        field.choices = [("", _("All")), ("none", _("No recipient"))] + [
            (str(r.pk), r.name) for r in recipients
        ]
        field.widget.method_by_value = {str(r.pk): r.payment_method_id for r in recipients}

    def clean_recipient(self):
        value = self.cleaned_data.get("recipient") or ""
        if value in ("", "none"):
            return value or "all"
        return self._recipients[value]

    def clean(self):
        cleaned = super().clean()
        date_from, date_to = cleaned.get("date_from"), cleaned.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", _("'Date from' must be on or before 'Date to'."))
        recipient = cleaned.get("recipient")
        payment_method = cleaned.get("payment_method")
        if (
            isinstance(recipient, PaymentRecipient)
            and payment_method is not None
            and recipient.payment_method_id != payment_method.pk
        ):
            self.add_error(
                "recipient", _("Selected recipient does not belong to this payment method.")
            )
        return cleaned

    def report_kwargs(self) -> dict:
        """Keyword arguments for ``build_payment_method_report`` (form must be valid)."""
        data = self.cleaned_data
        return {
            "payment_method": data["payment_method"],
            "recipient": data["recipient"],
            "date_from": data["date_from"],
            "date_to": data["date_to"],
            "kind": data.get("kind") or "all",
        }
