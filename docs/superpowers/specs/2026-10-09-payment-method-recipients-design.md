# Payment method recipients + payment methods report — Design

**Date:** 2026-10-09  
**Status:** Design approved in chat; awaiting written-spec review

## Problem

One payment method (e.g. **Jawwal Pay**) is received by several people (Ahmad, Raed, Ramez), each with their own wallet/account and their own statement. Today `PaymentMethod` has no notion of who received the money, so management cannot reconcile a recipient's statement against the sales and customer payments recorded in the system.

## Goals

1. Each payment method can have zero or more **named recipients**, managed from the payment method page.
2. When a payment method is chosen on the sales screen (and in customer payment flows), the user picks the recipient by name. One recipient → auto-selected; more than one → choice is required.
3. A new report **"Payment methods report"** lists the money received on a given method + recipient over a period, with details, totals and CSV export, for statement matching.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Storage | New model `PaymentRecipient` (FK to `PaymentMethod`); new nullable FK `payment_recipient` on `Sale`, `CustomerPayment`, `CustomerPaymentSubmission` |
| Recipient identity | Free-text name typed by management — **not** a system user / `EmployeeProfile` |
| Unrelated existing field | `employee_recipient` (cash held by an employee under "paid via employee") is untouched and unrelated |
| Selection rule | 0 recipients → unchanged behaviour; 1 active → auto-assigned; ≥2 active → required choice |
| Customer settlements | In scope: customer payments (direct and via approved submissions) carry a recipient and appear in the report |
| Double counting | Report sums **money movements**, not sales: direct sales + customer payments. On-account sales settled by a payment are shown only as details under that payment, never summed |
| Historical rows | Rows created before this feature keep `payment_recipient = NULL` and appear under "No recipient" |
| Deleting a recipient | Allowed only if unused; otherwise deactivate (`on_delete=PROTECT`) |
| Export | CSV export of the report |

## Data model

### `sales.PaymentRecipient` (new)

| Field | Type | Notes |
|-------|------|-------|
| `payment_method` | FK `PaymentMethod`, `on_delete=CASCADE`, `related_name="recipients"` | |
| `name` | `CharField(120)` | Shown on sales screen and report |
| `is_active` | `BooleanField(default=True)` | Inactive recipients are hidden from pickers but kept for history |
| `sort_order` | `PositiveIntegerField(default=0)` | Button order on the sales screen |

- `Meta.ordering = ("sort_order", "name")`
- `UniqueConstraint(payment_method, name)` (case-sensitive is fine; names are short Arabic first names).
- `PaymentMethod.active_recipients()` helper returns active recipients in order.

`CASCADE` on the method side is safe because `PaymentMethod` deletion is already blocked by `PROTECT` from `Sale` / `CustomerPayment` once used; unused methods may take their recipients with them.

### New FKs

- `Sale.payment_recipient` — `FK PaymentRecipient, null=True, blank=True, on_delete=PROTECT, related_name="sales"`
- `CustomerPayment.payment_recipient` — same, `related_name="customer_payments"`
- `CustomerPaymentSubmission.payment_recipient` — same, `related_name="payment_submissions"`

### Integrity rule (enforced in forms + services)

If `payment_recipient` is set, `payment_recipient.payment_method_id == payment_method_id`. Whenever `payment_method` is cleared (on-account, paid via employee, settlement reversal), `payment_recipient` is cleared too.

## Recipient resolution (single shared helper)

`sales/recipients.py`:

```python
def resolve_payment_recipient(payment_method, chosen_recipient) -> PaymentRecipient | None
```

- `payment_method is None` → `None`.
- Method has 0 active recipients → `None` (any chosen value is rejected as invalid).
- Method has exactly 1 active recipient → that recipient (chosen value ignored if it matches, error if it doesn't).
- Method has ≥2 active recipients → `chosen_recipient` required, must be active and belong to the method; otherwise `ValidationError("Pick who received the payment.")`.

Used by every form/service that accepts a payment method, so the rule lives in one place.

## Management UI — payment methods

**Edit page** (`templates/sales/payment_method_form.html`, `sales/views/payment_methods.py`):

- New card **"Recipients"** below the method fields, implemented as an inline model formset over `PaymentRecipient` (`name`, `is_active`, `sort_order`, delete checkbox) with one extra empty row and an "add recipient" button that clones the empty form.
- Deleting a recipient that is referenced by any sale / payment / submission is refused with a message suggesting deactivation (catch `ProtectedError` per row, keep the rest of the save).
- Create page shows the same card so recipients can be added in one step.

**List page** (`payment_method_list.html`): a "Recipients" column listing active recipient names (comma-separated), or "—".

Admin: register `PaymentRecipient` inline under `PaymentMethodAdmin`.

## Sales entry (employee) — `templates/sales/employee_entry.html`

- Each payment tile gets `data-recipients='[{"id":1,"name":"Ahmad"}, …]'` (active recipients, JSON-escaped) rendered by the view.
- New hidden input `payment_recipient` (`id_payment_recipient`) on `EmployeeSaleForm`.
- New container `#payment-recipient-picker` directly under `#payment-tiles`:
  - 0 recipients → hidden, hidden input cleared.
  - 1 recipient → shows a read-only chip "Received by: Ahmad", hidden input set.
  - ≥2 → row of toggle buttons (same chip styling as payment tiles); clicking sets the hidden input; nothing preselected.
- Switching tile, toggling on-account or paid-via-employee clears the picker and the hidden input.
- After a validation error, the picker is restored from the posted value (same mechanism as the existing tile restore).
- Server side: `EmployeeSaleForm.clean()` calls `resolve_payment_recipient`; `create_sale(...)` accepts and stores `payment_recipient`.

### Customer payment submission modal (`#rdCustomerPaySubModal`)

Same picker pattern under `#rd-pay-sub-payment-tiles` with hidden `id_pay_sub_payment_recipient`; `EmployeeCustomerPaymentSubmissionForm` resolves it; `submit_customer_payment_submission` stores it. On approval, `_apply_customer_payment` copies it onto the created `CustomerPayment`.

### Management forms

- `CustomerPaymentForm` (manager records a customer payment): `payment_recipient` select, filtered client-side by selected method (small inline script, options carry `data-method`), validated by `resolve_payment_recipient`.
- `ManagementSaleEditForm` and `EmployeeSaleEditForm`: same select next to payment method. `update_sale_fields` saves `payment_recipient` and adds it to the audited field list.
- Submission approval screen shows the recipient read-only.

### Settlement flow (`customers/services.py`)

- FIFO settlement keeps copying `payment_method` onto settled on-account sales (existing behaviour) **and** copies `payment_recipient` from the settling payment, so the sale detail pages stay consistent.
- Every place that clears `payment_method` / `customer_payment` on reversal (lines ~241, ~696) also clears `payment_recipient`.

## Report — "Payment methods report"

**Route:** `reports:payment_methods_report` → `/management/reports/payment-methods/`; nav link in the Reports group of `templates/partials/management_nav.html`. Management-only, same decorator as other reports.

### Filters (GET form, htmx like the Sales report)

| Filter | Values | Default |
|--------|--------|---------|
| `payment_method` | active + inactive methods | required — page shows a prompt until chosen |
| `recipient` | "all" / a recipient of the chosen method (incl. inactive) / "none" (No recipient) | all |
| `date_from`, `date_to` | dates (inclusive, local time) | first day of current month → today |
| `kind` | all / sales / settlements | all |

The recipient select renders every recipient as an `<option data-method="…">`; a small inline script hides options not belonging to the selected method and resets the value to "all" when the method changes (same pattern as `CustomerPaymentForm`).

### Rows (money movements)

1. **Direct sales**: `Sale` with `payment_method = M`, `on_account = False`, `status != CANCELLED`, `created_at` in range, recipient filter applied. Status shown: Paid / Pending confirmation.
2. **Customer payments**: `CustomerPayment` with `payment_method = M`, `created_at` in range, recipient filter applied. Pending (unapproved) submissions are **not** included.
3. **Settled sales** are never rows: for each customer payment row, the sales with `customer_payment = that payment` are listed in an expandable detail ("Show settled sales") and excluded from all totals.

Merged and sorted by `created_at` ascending (statement order), tie-break by type then id.

### Columns

| Column | Sale | Customer payment |
|--------|------|------------------|
| Date/time | `created_at` | `created_at` |
| Type | Sale | Settlement |
| Name | `payer_name` | `customer.name` |
| Number | `reference_number` | — |
| Company / product | ✓ | — |
| Recipient | name or "No recipient" | same |
| Employee | `created_by` | `created_by` |
| Amount | `sell_price_actual` | `amount` |
| Status | Paid / Pending confirmation | Approved |

Desktop table + mobile cards, following `templates/reports/partials/sales_report_results.html`.

### Totals (over the full filtered set, not the page)

- Total received + count of movements
- Sales subtotal, settlements subtotal
- Pending-confirmation subtotal (direct sales with `status = PENDING`)
- When recipient = all: a small per-recipient breakdown table (name → total, count), including "No recipient" if non-zero

### Pagination

50 rows per page via `paginate_request` on the merged list (two querysets evaluated with `values()`-style rows and merged in Python; volume per method per period is small enough — revisit with a UNION query only if it proves slow).

### CSV export

Button "Export Excel" → same view and filters with `?export=csv`, rendered via `core/csv_export.csv_response` (already writes the UTF-8 BOM Excel needs for Arabic). Exports **all** filtered rows, not just the current page. Columns = table columns + a `settled_sales` text column for payment rows (e.g. `#123 50.00; #130 20.00`).

## Translations

All new UI strings via `{% trans %}` / `gettext`, Arabic added to `tools/fill_ar_translations.py`, then `makemessages` → fill script → `compilemessages`. Recipient names are user data and not translated.

## Error handling

- Method with ≥2 recipients and none chosen → field error "Pick who received the payment." on the sales form / modal; picker highlighted.
- Recipient not belonging to the method / inactive → generic invalid-choice error (tampered POST).
- Deactivating the only recipient of a method returns that method to "no recipient" behaviour; existing rows keep their recipient.
- Report with no method chosen → empty state prompting to choose one; no queries run.

## Testing (Django test runner, `manage.py test`)

- `resolve_payment_recipient`: 0 / 1 / ≥2 recipients, inactive, wrong method.
- Employee sale entry: auto-assign with one recipient; error without choice with two; stored on sale; cleared when on-account / paid via employee.
- Submission → approval copies recipient to `CustomerPayment`; FIFO settlement copies recipient to settled sales; reversal clears it.
- Payment method edit: add/rename/deactivate recipients; deleting a used recipient refused.
- Report: direct sale counted; cancelled excluded; on-account sale settled by a payment counted **once** (payment row only, sale in details); recipient filter incl. "none"; date range bounds; per-recipient breakdown; CSV contents and BOM.

## Out of scope

- Opening balances / reconciliation status per recipient (marking rows as matched)
- Uploading recipient statements for automatic matching
- Recipients on expenses or supplier payments
- Backfilling recipients on historical rows

## Success criteria

- Jawwal Pay with recipients Ahmad / Raed / Ramez: choosing Jawwal Pay on the sales screen shows three buttons and the sale cannot be saved without picking one; a method with a single recipient saves without any extra click.
- A customer pays a 50 debt via Jawwal Pay to Ahmad: the report for Jawwal Pay / Ahmad shows one 50 settlement row (with the settled sale in its details), total 50.
- Report totals for a recipient and period equal the sum of that recipient's real incoming transfers, and the CSV opens correctly in Excel.
