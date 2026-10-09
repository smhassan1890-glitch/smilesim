# Payment Method Recipients + Payment Methods Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each payment method have named recipients that are picked on every payment entry, and add a "Payment methods report" report that lists money received per method + recipient for statement matching.

**Architecture:** New `sales.PaymentRecipient` model plus a nullable `payment_recipient` FK on `Sale`, `CustomerPayment` and `CustomerPaymentSubmission`. One helper (`sales/recipients.py::resolve_payment_recipient`) enforces the 0 / 1 / many rule for every form and service. The report is a pure query module (`reports/payment_methods.py`) that merges direct sales and customer payments (settled on-account sales are details, never summed), rendered by a thin view with htmx results and CSV export.

**Tech Stack:** Django (function views, ModelForms, inline formsets), htmx, Bootstrap 5.3, inline vanilla JS, Django test runner.

**Spec:** `docs/superpowers/specs/2026-10-09-payment-method-recipients-design.md`

## Global Constraints

- Work directly on `main` (user: no feature branches). Do **not** commit: the user has asked to hold commits; every "Commit" step below is replaced by "Stage only" (`git add <files>`) until the user says otherwise.
- Run tests with `.venv\Scripts\python.exe manage.py test <label> --parallel 1`. Known unrelated failure on Windows: `core.tests.MediaServingTests.test_serve_media_sets_webp_content_type` (file lock in cleanup).
- Services raise `ValueError` with a translatable message (project convention); forms turn it into a field error.
- All UI copy via `{% trans %}` / `gettext_lazy`; Arabic added to `tools/fill_ar_translations.py` (Task 9).
- Recipient names are user data — never passed through `tdb` or translated.
- Integrity rule: `payment_recipient` is set only when `payment_method` is set and `payment_recipient.payment_method_id == payment_method_id`; clearing `payment_method` always clears `payment_recipient`.
- Required-choice error copy: `_("Pick who received the payment.")`.
- Report page size: 50. Report default period: first day of current month → today (local date).
- New migrations: `sales/migrations/0016_payment_recipients.py`, `customers/migrations/0006_payment_recipients.py` (depends on sales 0016).

## Review Focus

1. **Recipient from another method posted by a stale/tampered form** → rejected, sale not saved. Test in Task 2 (`test_rejects_recipient_of_other_method`) and Task 4 (`test_post_with_foreign_recipient_is_rejected`).
2. **Switching tile / toggling on-account after picking a recipient** → hidden recipient cleared so an on-account sale never carries a recipient. Server-side guard tested in Task 4 (`test_on_account_ignores_posted_recipient`).
3. **Customer payment settles several on-account sales, then is deleted** → all those sales lose `payment_recipient` and the report no longer lists them as details. Task 6 (`test_delete_payment_clears_recipient_on_settled_sales`).
4. **Sale edited from pending to another method** → recipient revalidated against the new method; a single-recipient method auto-assigns. Task 5 (`test_edit_switch_method_auto_assigns_single_recipient`).
5. **Date range boundary in local time (sale at 23:30 local on `date_to`)** → included. Task 7 (`test_date_to_is_inclusive_local_day`).

---

### Task 1: `PaymentRecipient` model and FKs

**Files:**
- Modify: `sales/models.py` (after `PaymentMethod`, and `Sale` fields after `payment_method`)
- Modify: `customers/models.py` (`CustomerPayment`, `CustomerPaymentSubmission`, after `payment_method`)
- Modify: `sales/admin.py` (inline under `PaymentMethodAdmin`)
- Create: `sales/migrations/0016_payment_recipients.py`, `customers/migrations/0006_payment_recipients.py` (via `makemigrations`)
- Test: `sales/tests_recipients.py` (new)

**Interfaces:**
- Produces:
  - `sales.models.PaymentRecipient(payment_method: FK PaymentMethod CASCADE related_name="recipients", name: CharField(120), is_active: bool=True, sort_order: PositiveInteger=0)`; `Meta.ordering = ("sort_order", "name")`; `UniqueConstraint(fields=["payment_method", "name"], name="uniq_recipient_name_per_method")`; `__str__` → `name`.
  - `PaymentMethod.active_recipients(self) -> QuerySet[PaymentRecipient]` (active, ordered).
  - `Sale.payment_recipient`, `CustomerPayment.payment_recipient`, `CustomerPaymentSubmission.payment_recipient`: `FK PaymentRecipient, PROTECT, null=True, blank=True`, related names `sales`, `customer_payments`, `payment_submissions`, verbose name `_("payment recipient")`.

- [ ] **Step 1: Write failing tests** in `sales/tests_recipients.py`, class `PaymentRecipientModelTests`:
  - `test_active_recipients_ordered_and_filtered`: method with recipients (`"Ramez"`, sort 2), (`"Ahmad"`, sort 1), (`"Raed"`, sort 1, inactive) → `[r.name for r in pm.active_recipients()] == ["Ahmad", "Ramez"]`.
  - `test_duplicate_name_same_method_rejected`: second `"Ahmad"` on same method raises `IntegrityError` (wrap in `transaction.atomic()`).
  - `test_used_recipient_cannot_be_deleted`: sale created with `payment_recipient=r` (set via `Sale.objects.filter(pk=..).update(...)`) → `r.delete()` raises `ProtectedError`.
- [ ] **Step 2: Run** `.venv\Scripts\python.exe manage.py test sales.tests_recipients --parallel 1` → FAIL (import error).
- [ ] **Step 3: Implement** the model, method and FKs; register `PaymentRecipientInline(admin.TabularInline)` with fields `name, is_active, sort_order`.
- [ ] **Step 4: Generate migrations**: `.venv\Scripts\python.exe manage.py makemigrations sales customers -n payment_recipients`; confirm file names match Global Constraints.
- [ ] **Step 5: Run** the test module → PASS; `manage.py makemigrations --check --dry-run` → "No changes detected".
- [ ] **Step 6: Stage only.**

---

### Task 2: Recipient resolution helper

**Files:**
- Create: `sales/recipients.py`
- Test: `sales/tests_recipients.py` (class `ResolvePaymentRecipientTests`)

**Interfaces:**
- Consumes: `PaymentRecipient`, `PaymentMethod.active_recipients()` (Task 1).
- Produces:
  - `resolve_payment_recipient(payment_method: PaymentMethod | None, chosen: PaymentRecipient | None) -> PaymentRecipient | None` — raises `ValueError(_("Pick who received the payment."))` when ≥2 active and none chosen; `ValueError(_("Selected recipient does not belong to this payment method."))` when chosen is inactive or of another method, or chosen given while the method has no active recipients.
  - `recipients_json(payment_method: PaymentMethod) -> str` — `json.dumps([{"id": r.pk, "name": r.name} for r in active], ensure_ascii=False)`; used in `data-recipients` attributes (template escapes it).

- [ ] **Step 1: Write failing tests:**
  - `test_none_method_returns_none` → `resolve_payment_recipient(None, None) is None`.
  - `test_no_recipients_returns_none`.
  - `test_single_recipient_auto_assigned` → returns it with `chosen=None`, and with `chosen=it`.
  - `test_many_requires_choice` → `assertRaisesMessage(ValueError, "Pick who received the payment.")`.
  - `test_many_returns_chosen`.
  - `test_rejects_recipient_of_other_method` (Review Focus 1).
  - `test_rejects_inactive_recipient`.
  - `test_recipients_json_lists_active_only` → `json.loads(...) == [{"id": a.pk, "name": "Ahmad"}]`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** both functions.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Stage only.**

---

### Task 3: Manage recipients on the payment method pages

**Files:**
- Modify: `sales/forms.py` (add formset after `PaymentMethodForm`)
- Modify: `sales/views/payment_methods.py` (create/edit/list)
- Modify: `templates/sales/payment_method_form.html`, `templates/sales/payment_method_list.html`
- Test: `sales/tests_recipients.py` (class `PaymentMethodRecipientsViewTests`)

**Interfaces:**
- Consumes: `PaymentRecipient` (Task 1).
- Produces: `PaymentRecipientFormSet = inlineformset_factory(PaymentMethod, PaymentRecipient, fields=["name", "is_active", "sort_order"], extra=1, can_delete=True)` with widgets `form-control form-control-sm` / `form-check-input`; formset prefix `"recipients"`.

- [ ] **Step 1: Write failing tests** (management user via `UserProfile.Role.MANAGEMENT`, as in `reports/tests.py::_ReportsBase`):
  - `test_create_with_recipients`: POST name `"Jawwal Pay"` + management form `recipients-TOTAL_FORMS=3` with names Ahmad/Raed/Ramez → `PaymentMethod.objects.get(name="Jawwal Pay").recipients.count() == 3`.
  - `test_edit_renames_and_deactivates`.
  - `test_delete_used_recipient_is_refused`: recipient referenced by a sale, POST with `recipients-0-DELETE=on` → recipient still exists, response (follow) contains the message `"is used by existing records"`; other changes in the same POST are saved.
  - `test_list_shows_active_recipient_names`: list page contains `"Ahmad"` and not an inactive name.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Views bind `PaymentMethodForm` + `PaymentRecipientFormSet(instance=obj, prefix="recipients")`; save both inside `transaction.atomic()` when both valid. For deletions, iterate `formset.deleted_objects` yourself (`formset.save(commit=False)`), wrap each `obj.delete()` in `try/except ProtectedError` and add `messages.warning(_("“%(name)s” is used by existing records and was not deleted. Deactivate it instead."))`. List view: `prefetch_related(Prefetch("recipients", queryset=PaymentRecipient.objects.filter(is_active=True), to_attr="active_recipient_list"))`; new column "Recipients" joined with commas, or `—`.
  Template: new `rd-card` "Recipients" under the method fields; one row per form (name / sort / active / delete), hidden `empty_form` in a `<template id="recipient-empty-form">`, "Add recipient" button that clones it replacing `__prefix__` and bumps `TOTAL_FORMS` (inline script, ~15 lines).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Stage only.**

---

### Task 4: Recipient on employee sale entry

**Files:**
- Modify: `sales/services.py` (`create_sale`, `_SALE_AUDITED_FIELDS`)
- Modify: `sales/forms.py` (`EmployeeSaleForm`)
- Modify: `sales/views/employee.py` (`employee_entry`)
- Modify: `templates/sales/employee_entry.html` (payment section lines ~83–135; script functions `setPaidViaEmployee` ~728, `syncPaymentFromTile` ~759, `setOnAccount` ~781, tile click ~824, error-restore ~907)
- Modify: `static/css/app.css` (picker styles next to employee chip styles)
- Test: `sales/tests_recipients.py` (class `EmployeeEntryRecipientTests`)

**Interfaces:**
- Consumes: `resolve_payment_recipient`, `recipients_json` (Task 2).
- Produces:
  - `create_sale(..., payment_recipient: PaymentRecipient | None = None)` — stores it only for non-on-account, non-employee sales; re-validates with `resolve_payment_recipient(payment_method, payment_recipient)` (so services are safe without the form).
  - `"payment_recipient_id"` appended to `_SALE_AUDITED_FIELDS`.
  - `EmployeeSaleForm.payment_recipient = ModelChoiceField(queryset=PaymentRecipient.objects.filter(is_active=True), required=False, widget=HiddenInput(attrs={"id": "id_payment_recipient"}))`.
  - View context: each item of `payment_methods` gets attribute `recipients_json` (str); context key `selected_recipient_id` (str, from POST).

- [ ] **Step 1: Write failing tests** (employee user + acting profile as in `sales/tests.py` employee-entry tests; POST to `reverse("sales:employee_entry")`):
  - `test_single_recipient_auto_assigned_on_save`.
  - `test_two_recipients_without_choice_shows_error`: response 200, `Sale.objects.count() == 0`, contains `"Pick who received the payment."`.
  - `test_two_recipients_with_choice_saved`.
  - `test_post_with_foreign_recipient_is_rejected` (Review Focus 1).
  - `test_on_account_ignores_posted_recipient` (Review Focus 2): `on_account=1` + recipient id → saved sale has `payment_recipient_id is None`.
  - `test_tiles_carry_recipient_data`: GET contains `data-recipients=` and `Ahmad`.
  - `test_create_sale_service_rejects_missing_choice`: direct `create_sale(...)` with a 2-recipient method and no recipient raises `ValueError`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement form + service + view.** In `EmployeeSaleForm.clean()`: in the on-account and paid-via-employee branches set `cleaned["payment_recipient"] = None`; in the normal branch, when a method is present, `try: cleaned["payment_recipient"] = resolve_payment_recipient(payment_method, cleaned.get("payment_recipient")) except ValueError as exc: self.add_error("payment_recipient", str(exc))`. View passes `payment_recipient=form.cleaned_data.get("payment_recipient")` only for normal sales; prefetch active recipients for `payment_methods`.
- [ ] **Step 4: Implement template + JS.**
  - Each `.employee-payment-tile` gets `data-recipients="{{ pm.recipients_json }}"`.
  - Render `{{ form.payment_recipient }}` and `{{ form.payment_recipient.errors }}` next to `form.payment_method`.
  - Under `#payment-tiles` add `<div id="payment-recipient-picker" class="rd-recipient-picker" hidden>` with a label `{% trans "Received by" %}` and an empty `<div class="rd-recipient-picker__options" role="radiogroup">`.
  - New JS `renderRecipientPicker(tile)`: parse `data-recipients`; 0 → hide, clear hidden input; 1 → show a single non-interactive chip, set hidden input; ≥2 → buttons `.rd-recipient-chip` (`role="radio"`, `aria-checked`), none preselected unless it equals the hidden input's current value. Call it from `syncPaymentFromTile`; call `clearRecipientPicker()` from `setOnAccount(true)`, `setPaidViaEmployee(true)` and when no tile is active; on error-restore call `renderRecipientPicker` after the tile is restored.
  - CSS: `.rd-recipient-picker` (margin-top `.5rem`), `.rd-recipient-chip` reusing `.employee-chip` look; `.is-active` uses `--bs-primary` border/background tint like the active payment tile; when the field has errors add `.is-invalid` outline on the picker.
- [ ] **Step 5: Run** `manage.py test sales --parallel 1` → PASS (existing entry tests still green).
- [ ] **Step 6: Manual check** (runserver on 8080): Jawwal Pay with 3 recipients shows 3 buttons; with 1 shows the chip; toggling "on account" hides the picker.
- [ ] **Step 7: Stage only.**

---

### Task 5: Recipient on sale edit (management + employee)

**Files:**
- Modify: `sales/services.py` (`update_sale_fields`)
- Modify: `sales/forms.py` (`ManagementSaleEditForm`, `EmployeeSaleEditForm`)
- Modify: `sales/views/management.py` (`sale_edit`), `sales/views/employee.py` (`employee_sale_edit`)
- Modify: `templates/sales/sale_edit.html`, `templates/sales/employee_sale_edit.html`
- Test: `sales/tests_recipients.py` (class `SaleEditRecipientTests`)

**Interfaces:**
- Consumes: `resolve_payment_recipient` (Task 2).
- Produces:
  - `update_sale_fields(..., payment_recipient: PaymentRecipient | None = None)` — when the sale is on-account or paid via employee: sets both `payment_method` and `payment_recipient` to `None`; otherwise `payment_recipient = resolve_payment_recipient(payment_method, payment_recipient)`; `"payment_recipient"` added to `update_fields`.
  - `ManagementSaleEditForm.Meta.fields` gains `"payment_recipient"` (Select, queryset all recipients of active methods, `select_related("payment_method")`, label `{method} — {name}` via `label_from_instance`; each `<option>` gets `data-method` through a custom `Select.create_option`). `clean()` resolves via the helper and adds field errors. `EmployeeSaleEditForm` deletes `payment_recipient` together with `payment_method` for on-account / employee sales.

- [ ] **Step 1: Write failing tests:**
  - `test_edit_sets_recipient`.
  - `test_edit_switch_method_auto_assigns_single_recipient` (Review Focus 4).
  - `test_edit_on_account_sale_keeps_recipient_none`.
  - `test_update_service_records_audit_change`: audit row for the update has `"payment_recipient_id"` in `changes`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** forms, service and views (pass `payment_recipient=form.cleaned_data.get("payment_recipient")`). Templates render the field under payment method plus a 10-line inline script that hides options whose `data-method` differs from the selected method and resets the value if hidden.
- [ ] **Step 4: Run** `manage.py test sales customers audit --parallel 1` → PASS (existing `update_sale_fields` callers use the default `None`).
- [ ] **Step 5: Stage only.**

---

### Task 6: Recipient on customer payments, submissions and settlements

**Files:**
- Modify: `customers/services.py` (`_apply_customer_payment`, `record_customer_payment`, `submit_customer_payment_submission`, `approve_customer_payment_submission`, FIFO block ~866–883, `sync_on_account_charge_for_sale` reset ~237–252, `delete_customer_payment` ~692–707)
- Modify: `customers/forms.py` (`EmployeeCustomerPaymentSubmissionForm`, `CustomerPaymentForm`)
- Modify: `sales/views/employee.py` (`employee_submit_customer_payment_submission`), `customers/views/actions.py` (`customer_record_payment`), `customers/views/crud.py` (detail context: methods with recipients)
- Modify: `templates/sales/employee_entry.html` (modal tiles ~351, script ~396–520), `templates/customers/customer_detail.html` (~178–180), `templates/customers/payment_submissions_list.html` (show recipient)
- Test: `customers/tests_recipients.py` (new)

**Interfaces:**
- Consumes: `resolve_payment_recipient`, `recipients_json` (Task 2); `CustomerPayment.payment_recipient`, `CustomerPaymentSubmission.payment_recipient` (Task 1).
- Produces:
  - `record_customer_payment(..., payment_recipient=None)`, `submit_customer_payment_submission(..., payment_recipient=None)`, `_apply_customer_payment(..., payment_recipient=None)` — each resolves via the helper when not paid via employee, else forces `None`; stored on the created row; included in audit `changes` as `payment_recipient_id`.
  - `approve_customer_payment_submission` passes `payment_recipient=sub.payment_recipient`.
  - FIFO settlement sets `sale.payment_recipient = fallback_payment.payment_recipient` and adds `"payment_recipient"` to `update_fields`; both reset sites set it to `None` and add it to `update_fields`.
  - `EmployeeCustomerPaymentSubmissionForm.payment_recipient` hidden (`id_pay_sub_payment_recipient`); `CustomerPaymentForm.payment_recipient` Select with `data-method` options (same widget as Task 5).

- [ ] **Step 1: Write failing tests** (reuse helpers: `create_customer`, `create_sale(on_account=True, customer=...)`, `approve_sale`):
  - `test_record_payment_stores_recipient`.
  - `test_record_payment_requires_choice_for_multi_recipient_method` → `ValueError`.
  - `test_submission_then_approval_copies_recipient`.
  - `test_fifo_settlement_copies_recipient_to_sales`: on-account sale 50 approved, payment 50 with recipient → sale `payment_recipient_id == r.pk`.
  - `test_delete_payment_clears_recipient_on_settled_sales` (Review Focus 3): two settled sales → both `payment_recipient_id is None` after `delete_customer_payment`.
  - `test_price_edit_unsettle_clears_recipient`: on-account sale 50 settled by a 50 payment with recipient, then `update_sale_fields` raises the price to 60 → sale is `PENDING` (FIFO can no longer cover it) with `payment_method_id is None` and `payment_recipient_id is None`.
  - `test_employee_modal_post_requires_choice`: POST to `sales:employee_submit_customer_payment_submission` with a 2-recipient method and no recipient → no submission created, error message flashed.
- [ ] **Step 2: Run** `manage.py test customers.tests_recipients --parallel 1` → FAIL.
- [ ] **Step 3: Implement services, forms, views.**
- [ ] **Step 4: Implement templates.** Modal: `.rd-pay-sub-pm-tile` gets `data-recipients`; add `#rd-pay-sub-recipient-picker` under `#rd-pay-sub-payment-tiles` and reuse `renderRecipientPicker` from Task 4 by parameterising it as `renderRecipientPicker(tile, pickerEl, hiddenInput)` (refactor the Task 4 call sites accordingly). Customer detail: render `payment_form.payment_recipient` under the method select with the same filter script as Task 5 (extract that script to `static/js/recipient-select-filter.js` and include it in both templates). Submissions list: show `sub.payment_recipient.name` under the method name when set.
- [ ] **Step 5: Run** `manage.py test customers sales employees --parallel 1` → PASS.
- [ ] **Step 6: Stage only.**

---

### Task 7: Report query module

**Files:**
- Create: `reports/payment_methods.py`
- Test: `reports/tests_payment_methods.py` (new; reuse `_ReportsBase` from `reports/tests.py`)

**Interfaces:**
- Consumes: models from Tasks 1 and 6.
- Produces:
  ```python
  RecipientFilter = Literal["all", "none"] | PaymentRecipient
  Kind = Literal["all", "sales", "settlements"]

  @dataclass
  class ReportRow:
      kind: Literal["sale", "payment"]
      pk: int
      created_at: datetime
      name: str               # sale.payer_name / payment.customer.name
      reference: str          # sale.reference_number / ""
      company_product: str    # "Company · Product" / ""
      recipient_name: str     # "" when none
      employee: str           # created_by.username
      amount: Decimal
      is_pending: bool        # sale.status == PENDING
      settled_sales: list[Sale]  # payments only

  @dataclass
  class RecipientTotal:
      recipient_name: str     # "" == no recipient
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
      by_recipient: list[RecipientTotal]   # only filled when recipient == "all"

  def build_payment_method_report(*, payment_method: PaymentMethod, recipient: RecipientFilter,
                                  date_from: date, date_to: date, kind: Kind) -> PaymentMethodReport
  ```
  Sales query: `Sale.objects.filter(payment_method=pm, on_account=False).exclude(status=CANCELLED)`; payments query: `CustomerPayment.objects.filter(payment_method=pm)` with `prefetch_related("settled_sales__company", "settled_sales__product")`; both filtered by `created_at__date__range=(date_from, date_to)` (TZ-aware `__date` uses the active local timezone) and by recipient (`payment_recipient=r` / `payment_recipient__isnull=True`). Rows merged and sorted by `(created_at, kind == "payment", pk)`.

- [ ] **Step 1: Write failing tests:**
  - `test_direct_sale_counted`.
  - `test_cancelled_sale_excluded`.
  - `test_settled_on_account_sale_counted_once`: on-account 50 approved, payment 50 → `report.total == 50`, one row of kind `"payment"`, `rows[0].settled_sales == [sale]`.
  - `test_recipient_filter_specific_and_none`.
  - `test_kind_filter_sales_only`.
  - `test_pending_total`: one pending + one paid sale → `pending_total` equals the pending amount.
  - `test_by_recipient_breakdown`: Ahmad 30 + Raed 20 + no-recipient 10 → three `RecipientTotal`s with those totals.
  - `test_rows_sorted_ascending`.
  - `test_date_to_is_inclusive_local_day` (Review Focus 5): sale with `created_at` updated to 23:30 local on `date_to` is included; one at 00:10 the next day is not.
- [ ] **Step 2: Run** `manage.py test reports.tests_payment_methods --parallel 1` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Stage only.**

---

### Task 8: Report page, navigation and CSV export

**Files:**
- Modify: `reports/forms.py` (new `PaymentMethodReportForm`)
- Modify: `reports/views.py` (new `payment_methods_report`), `reports/urls.py`
- Create: `templates/reports/payment_methods_report.html`, `templates/reports/partials/payment_methods_report_results.html`
- Modify: `templates/partials/management_nav.html` (Reports group, after "Sales report")
- Test: `reports/tests_payment_methods.py` (class `PaymentMethodsReportViewTests`)

**Interfaces:**
- Consumes: `build_payment_method_report` and dataclasses (Task 7); `paginate_request(request, list, per_page=50)`; `core.csv_export.csv_response(filename_stem, headers, row_iter)`, `fmt_dt`.
- Produces:
  - URL `path("management/reports/payment-methods/", views.payment_methods_report, name="payment_methods_report")`.
  - `PaymentMethodReportForm` fields: `payment_method` (ModelChoice over all methods, `required=False`), `recipient` (ChoiceField: `""` = all, `"none"`, recipient pks; choices built in `__init__` from all recipients, options carry `data-method`), `date_from`, `date_to` (DateField, defaults per Global Constraints applied in the view when absent), `kind` (`all`/`sales`/`settlements`). Method `report_kwargs() -> dict` returning the keyword arguments for `build_payment_method_report`; `clean()` rejects `date_from > date_to` and a recipient that does not belong to the chosen method.

- [ ] **Step 1: Write failing tests:**
  - `test_page_without_method_shows_prompt`: GET → 200, contains `"Choose a payment method"`, no rows table.
  - `test_results_partial_on_htmx`: with `HTTP_HX_REQUEST="true"` → template `reports/partials/payment_methods_report_results.html` used.
  - `test_totals_rendered`.
  - `test_csv_export`: `?payment_method=<pk>&export=csv` → `Content-Type` starts with `text/csv`, body starts with `"\ufeff"`, header row contains `"Recipient"` translated label, a payment row's last column contains `#<sale.pk>`.
  - `test_non_management_forbidden`: employee user → redirect/403 like other reports.
  - `test_nav_link_present`: dashboard HTML contains `reverse("reports:payment_methods_report")`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement form, view and URL.** View: invalid/missing method → render with `report=None`; `export=csv` → stream all rows (columns: date, type, name, number, company/product, recipient, employee, amount, status, settled sales `#pk amount; …`); htmx → partial; else full page.
- [ ] **Step 4: Implement templates** following `templates/reports/sales_report.html` + `partials/sales_report_results.html`: filter card (`partials/filter_card_open.html` / `filter_card_close.html`, htmx GET to `#payment-methods-report-results`), recipient select filtered by `static/js/recipient-select-filter.js` (Task 6), "Export Excel" button linking to the current query + `export=csv`. Results: KPI row (total + count, sales subtotal, settlements subtotal, pending subtotal) using the dashboard `.rd-stat` cards; per-recipient table when `report.by_recipient`; desktop table with columns from the spec and a `<details>` "Show settled sales" under payment rows; mobile cards; `partials/pagination.html`. Rows with `is_pending` show the existing pending status badge.
- [ ] **Step 5: Add nav link** "Payment methods report" with an `is-active` check on `un == 'payment_methods_report'`.
- [ ] **Step 6: Run** `manage.py test reports --parallel 1` → PASS.
- [ ] **Step 7: Manual check** at `http://localhost:8080/ar/management/reports/payment-methods/` with Jawwal Pay / Ahmad; open the CSV in Excel and confirm Arabic renders.
- [ ] **Step 8: Stage only.**

---

### Task 9: Arabic translations and full verification

**Files:**
- Modify: `tools/fill_ar_translations.py`, `locale/ar/LC_MESSAGES/django.po`, `locale/ar/LC_MESSAGES/django.mo`

- [ ] **Step 1:** `.venv\Scripts\python.exe manage.py makemessages -l ar --ignore=.venv`.
- [ ] **Step 2:** Add an Arabic translation for every new msgid to the `AR` dict, at minimum: `"payment recipient"`, `"Recipients"`, `"Add recipient"`, `"Received by"`, `"Pick who received the payment."`, `"Selected recipient does not belong to this payment method."`, `"Payment methods report"`, `"No recipient"`, `"Sale"`, `"Settlement"`, `"Show settled sales"`, `"Pending confirmation"`, `"Total received"`, `"Choose a payment method to see the report."`, `"Export Excel"`; then `.venv\Scripts\python.exe tools/fill_ar_translations.py`.
- [ ] **Step 3:** `.venv\Scripts\python.exe manage.py compilemessages --ignore=.venv`; grep the `.po` for remaining empty `msgstr ""` among the new msgids → none.
- [ ] **Step 4:** Full suite `.venv\Scripts\python.exe manage.py test --parallel 1` → only the known Windows media-lock error; `manage.py check` and `makemigrations --check --dry-run` clean.
- [ ] **Step 5: Stage only**, then report to the user and ask whether to commit.
