from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils.translation import gettext_lazy as _

from companies.models import Company, Product
from sales.models import PaymentMethod, PaymentRecipient, Sale
from sales.phone_validation import validate_sale_phone_prefix
from sales.recipients import resolve_edited_payment_recipient, resolve_payment_recipient

User = get_user_model()


class RecipientSelect(forms.Select):
    """Select whose recipient options carry ``data-method`` for client-side filtering."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-method"] = str(instance.payment_method_id)
        return option


class RecipientChoiceField(forms.ModelChoiceField):
    """Recipient choices labelled ``"{method} — {recipient}"``; needs ``select_related("payment_method")``."""

    def label_from_instance(self, obj):
        return f"{obj.payment_method.name} — {obj.name}"


def recipient_choice_queryset(*, include_pk=None):
    """Active recipients of active methods, plus ``include_pk`` (a record's current recipient)."""
    condition = Q(is_active=True, payment_method__is_active=True)
    if include_pk:
        condition |= Q(pk=include_pk)
    return (
        PaymentRecipient.objects.filter(condition)
        .select_related("payment_method")
        .order_by("payment_method__name", "sort_order", "name")
    )


class EmployeeSaleForm(forms.Form):
    company = forms.ModelChoiceField(
        label=_("Company"),
        queryset=Company.objects.filter(is_active=True),
        widget=forms.HiddenInput(attrs={"id": "id_company"}),
    )
    product = forms.ModelChoiceField(
        label=_("Product"),
        queryset=Product.objects.none(),
        widget=forms.HiddenInput(attrs={"id": "id_product"}),
    )
    reference_number = forms.CharField(
        label=_("Phone or shipment number"),
        max_length=64,
        widget=forms.TextInput(
            attrs={
                "id": "id_reference_number",
                "class": "form-control form-control-sm",
                "autocomplete": "off",
                "inputmode": "tel",
            }
        ),
    )
    payer_name = forms.CharField(
        label=_("Payer name"),
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "id": "id_payer_name",
                "class": "form-control form-control-sm",
                "autocomplete": "off",
                "autocapitalize": "words",
                "spellcheck": "false",
            }
        ),
    )
    sell_price_actual = forms.DecimalField(
        label=_("Selling price"),
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-sm",
                "step": "0.01",
                "min": "0",
                "id": "id_sell_price_actual",
            }
        ),
    )
    payment_method = forms.ModelChoiceField(
        label=_("Payment method"),
        queryset=PaymentMethod.objects.filter(is_active=True),
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_payment_method"}),
    )
    payment_recipient = forms.ModelChoiceField(
        label=_("Received by"),
        queryset=PaymentRecipient.objects.filter(is_active=True),
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_payment_recipient"}),
    )
    on_account = forms.BooleanField(
        label=_("On account"),
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_on_account"}),
    )
    paid_via_employee = forms.BooleanField(
        label=_("Payment to employee"),
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_paid_via_employee"}),
    )
    employee_recipient = forms.ModelChoiceField(
        label=_("Employee"),
        queryset=None,
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_employee_recipient"}),
    )
    is_esim = forms.BooleanField(
        label="",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "id": "id_is_esim",
                "class": "form-check-input",
            }
        ),
    )
    notes = forms.CharField(
        label=_("Notes"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        company_id = kwargs.pop("company_id", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        qs = Product.objects.filter(is_active=True).select_related("line", "line__company")
        if company_id:
            qs = qs.filter(line__company_id=company_id)
        self.fields["product"].queryset = qs
        from employees.models import EmployeeProfile
        from employees.services import get_acting_employee_profile

        self.acting_employee = get_acting_employee_profile(self.user)
        self.fields["employee_recipient"].queryset = EmployeeProfile.objects.filter(
            is_active=True
        ).select_related("user", "user__profile")

    def clean_reference_number(self):
        return validate_sale_phone_prefix(self.cleaned_data.get("reference_number") or "")

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company")
        product = cleaned.get("product")
        if company and product and product.line.company_id != company.id:
            raise forms.ValidationError(_("Selected product does not belong to the company."))
        on_account = bool(cleaned.get("on_account"))
        paid_via_employee = bool(cleaned.get("paid_via_employee"))
        payment_method = cleaned.get("payment_method")
        if paid_via_employee:
            from core.models import AppSettings

            if not AppSettings.load().sales_show_employee_payment:
                raise forms.ValidationError(
                    _("Payment to employee is disabled on the sales screen.")
                )
        if on_account and paid_via_employee:
            raise forms.ValidationError(
                _("Choose either on-account or payment to employee, not both.")
            )
        if paid_via_employee:
            cleaned["payment_method"] = None
            cleaned["payment_recipient"] = None
            self.errors.pop("payment_recipient", None)
            if not self.acting_employee:
                raise forms.ValidationError(
                    _("You are not registered as a payroll employee.")
                )
            cleaned["employee_recipient"] = self.acting_employee
        elif on_account:
            if payment_method is not None:
                cleaned["payment_method"] = None
            cleaned["payment_recipient"] = None
            self.errors.pop("payment_recipient", None)
            cleaned["employee_recipient"] = None
        else:
            cleaned["employee_recipient"] = None
            if payment_method is None:
                cleaned["payment_recipient"] = None
                self.add_error("payment_method", _("Pick a payment method."))
            elif "payment_recipient" not in self.errors:
                try:
                    cleaned["payment_recipient"] = resolve_payment_recipient(
                        payment_method, cleaned.get("payment_recipient")
                    )
                except ValueError as exc:
                    self.add_error("payment_recipient", str(exc))
        return cleaned


class ManagementSaleFilterForm(forms.Form):
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
    employee = forms.ModelChoiceField(
        label=_("Employee"),
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    payment_method = forms.ModelChoiceField(
        label=_("Payment method"),
        queryset=PaymentMethod.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        label=_("Status"),
        choices=[("", _("All"))] + list(Sale.Status.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date_from = forms.DateField(
        label=_("Date from"),
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    date_to = forms.DateField(
        label=_("Date to"),
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    esim = forms.ChoiceField(
        label=_("eSIM"),
        choices=[
            ("", _("All")),
            ("yes", _("eSIM only")),
            ("no", _("Non-eSIM")),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["product"].queryset = Product.objects.select_related("line", "line__company").order_by(
            "line__company__name", "line__sort_order", "line__name", "variant_label"
        )


class EmployeeRecentFilterForm(forms.Form):
    """Search/filter form for the employee 'My entries' page.

    Every field is optional. When the form is submitted blank the view
    falls back to "today only" so the employee never accidentally pulls
    their entire history. The form itself only validates input — it
    never reaches the database directly.
    """

    q = forms.CharField(
        label=_("Search"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": _("Phone, shipment number, payer name…"),
                "autocomplete": "off",
            }
        ),
    )
    company = forms.ModelChoiceField(
        label=_("Company"),
        queryset=Company.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    payment_method = forms.ModelChoiceField(
        label=_("Payment method"),
        queryset=PaymentMethod.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    status = forms.ChoiceField(
        label=_("Status"),
        choices=[("", _("All"))] + list(Sale.Status.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    date_from = forms.DateField(
        label=_("Date from"),
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control form-control-sm", "type": "date"}
        ),
    )
    date_to = forms.DateField(
        label=_("Date to"),
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control form-control-sm", "type": "date"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep dropdowns short and relevant — the employee shouldn't be
        # offered companies / payment methods that have been retired.
        self.fields["company"].queryset = Company.objects.filter(is_active=True).order_by("name")
        self.fields["payment_method"].queryset = (
            PaymentMethod.objects.filter(is_active=True).order_by("name")
        )

    def clean(self):
        cleaned = super().clean()
        df = cleaned.get("date_from")
        dt = cleaned.get("date_to")
        if df and dt and df > dt:
            raise forms.ValidationError(_("'Date from' must be on or before 'Date to'."))
        return cleaned

    def has_any_filter(self) -> bool:
        """True iff the user submitted at least one non-empty field.

        Used by the view to decide whether to default to "today only" or
        honour the (possibly empty) explicit submission.
        """
        if not self.is_bound or not self.is_valid():
            return False
        return any(self.cleaned_data.get(name) for name in self.fields)


class PaymentMethodForm(forms.ModelForm):
    class Meta:
        model = PaymentMethod
        fields = ["name", "icon", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "icon": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class _PaymentRecipientBaseFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        if "DELETE" in form.fields:
            form.fields["DELETE"].widget.attrs.update(
                {"class": "form-check-input", "aria-label": _("Delete")}
            )


PaymentRecipientFormSet = inlineformset_factory(
    PaymentMethod,
    PaymentRecipient,
    formset=_PaymentRecipientBaseFormSet,
    fields=["name", "is_active", "sort_order"],
    extra=1,
    can_delete=True,
    widgets={
        "name": forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "autocomplete": "off",
                "aria-label": _("Name"),
            }
        ),
        "is_active": forms.CheckboxInput(
            attrs={"class": "form-check-input", "aria-label": _("Active")}
        ),
        "sort_order": forms.NumberInput(
            attrs={
                "class": "form-control form-control-sm",
                "min": "0",
                "aria-label": _("Sort order"),
            }
        ),
    },
)


class ManagementSaleEditForm(forms.ModelForm):
    """Edit safe fields on an existing sale from the management UI.

    Excludes company / product / is_esim because those would invalidate
    the supplier-balance ledger snapshot taken at creation time.
    """

    payment_recipient = RecipientChoiceField(
        label=_("Received by"),
        queryset=PaymentRecipient.objects.none(),
        required=False,
        widget=RecipientSelect(
            attrs={"class": "form-select", "data-recipient-for": "id_payment_method"}
        ),
    )

    class Meta:
        model = Sale
        fields = [
            "payment_method",
            "payment_recipient",
            "payer_name",
            "reference_number",
            "sell_price_actual",
            "notes",
        ]
        widgets = {
            "payment_method": forms.Select(attrs={"class": "form-select"}),
            "payer_name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "reference_number": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "sell_price_actual": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].queryset = (
            PaymentMethod.objects.filter(is_active=True).order_by("name")
        )
        self.fields["payment_recipient"].queryset = recipient_choice_queryset(
            include_pk=self.instance.payment_recipient_id
        )

    def clean_reference_number(self):
        return validate_sale_phone_prefix(self.cleaned_data.get("reference_number") or "")

    def clean(self):
        cleaned = super().clean()
        sale = self.instance
        payment_method = cleaned.get("payment_method")
        if sale.paid_via_employee or sale.on_account:
            cleaned["payment_recipient"] = None
            self.errors.pop("payment_recipient", None)
            return cleaned
        if payment_method is None:
            cleaned["payment_recipient"] = None
            return cleaned
        if "payment_recipient" in self.errors:
            return cleaned
        try:
            cleaned["payment_recipient"] = resolve_edited_payment_recipient(
                sale, payment_method, cleaned.get("payment_recipient")
            )
        except ValueError as exc:
            self.add_error("payment_recipient", str(exc))
        return cleaned


class EmployeeSaleEditForm(ManagementSaleEditForm):
    """Employee edit form — hides payment method for on-account / employee payments."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sale = self.instance
        if sale and (sale.paid_via_employee or sale.on_account):
            del self.fields["payment_method"]
            del self.fields["payment_recipient"]

    def clean(self):
        cleaned = super().clean()
        sale = self.instance
        if sale and not sale.paid_via_employee and not sale.on_account:
            if not cleaned.get("payment_method"):
                self.add_error("payment_method", _("Pick a payment method."))
        return cleaned


class ManualDepositForm(forms.Form):
    amount = forms.DecimalField(
        label=_("Amount"),
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    notes = forms.CharField(
        label=_("Notes"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class BalanceAdjustmentForm(forms.Form):
    signed_amount = forms.DecimalField(
        label=_("Signed adjustment (+/-)"),
        max_digits=14,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    notes = forms.CharField(
        label=_("Notes"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
