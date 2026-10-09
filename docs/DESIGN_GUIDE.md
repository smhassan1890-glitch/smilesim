# Unified Design Guide — Recharge Desk

This is the reference for any new screen or component in the project. **Do not invent a new style** — use the classes and patterns in `static/css/design-system.css` and follow the reference templates below.

---

## 1. Source of truth for styling

| File | Role |
|--------|--------|
| `static/css/design-system.css` | Tokens, layout, cards, tables, tabs |
| `static/css/app.css` | Small extra customizations only — do not put new design logic here |
| Bootstrap 5 | Grid, forms, buttons — overridden via `--rd-*` variables |
| `static/js/data-ui.js` | Row action menus inside tables (`rd-actions-details`) |

**Golden rule:** if you need a new color, shadow or radius, add it first as a token in `design-system.css`, then use it — no inline styles unless strictly necessary (e.g. a fixed column width).

---

## 2. Management page structure

Every management page follows this order:

```html
{% extends "base_management.html" %}
{% block content %}

<!-- 1) Page header -->
<div class="rd-page-header d-flex flex-wrap justify-content-between align-items-start gap-3">
  <div>
    <h1 class="rd-heading-xl mb-1">{{ title }}</h1>
    <p class="rd-text-muted mb-0">Short page description.</p>
  </div>
  <!-- Optional: primary button -->
  <a class="btn btn-primary" href="...">Action</a>
</div>

<!-- 2) Section tabs (if any) -->
<ul class="nav nav-tabs mb-3 rd-section-tabs" role="tablist">...</ul>

<!-- 3) Filters / input forms -->
<div class="rd-card mb-3">
  <div class="rd-card-body rd-filter-bar">...</div>
</div>

<!-- 4) Main content (table or cards) -->
<div class="rd-card overflow-hidden rd-datagrid">...</div>

{% endblock %}
```

**Reference:** `templates/core/system_settings.html`, `templates/companies/company_detail.html`

---

## 3. Tabs

### When to use
- Splitting **a single section** into sub-screens (e.g. system settings, company details, employee details).

### Required markup
```html
<ul class="nav nav-tabs mb-3 rd-section-tabs" role="tablist">
  <li class="nav-item" role="presentation">
    <a class="nav-link active" href="?tab=general" role="tab">General</a>
  </li>
  ...
</ul>
```

### Not allowed
- `nav-pills` for navigating between app sections (only if explicitly requested).
- Custom tabs with inline CSS or colors other than `--bs-primary`.

**Reference:** `templates/core/system_settings.html`, `templates/employees/employee_detail.html`

---

## 4. Cards

| Class | Usage |
|--------|-----------|
| `rd-card` | Container for any content (form, table, KPI) |
| `rd-card-body` | Inner padding for forms and text |
| `rd-card-header` | Top title bar (rare — prefer `fw-semibold` inside the body) |

### Section-inside-a-tab pattern
```html
<div class="rd-card h-100">
  <div class="rd-card-body">
    <div class="mb-3">
      <div class="fw-semibold">Section title</div>
      <div class="rd-text-muted small">Short explanation.</div>
    </div>
    <!-- Form or content -->
  </div>
</div>
```

### Not allowed
- `app-card card` on new pages (legacy only — migrate gradually to `rd-card`).
- `rd-card p-3` without `rd-card-body`.

---

## 5. Tables

### Standard data pattern
```html
<div class="rd-card overflow-hidden rd-datagrid">
  <div class="rd-table-dual rd-datagrid-body">
    <div class="rd-data-shell">
      <div class="table-responsive border-0">
        <table class="table mb-0 align-middle rd-table-modern">
          <thead>...</thead>
          <tbody>...</tbody>
        </table>
      </div>
    </div>
  </div>
</div>
```

### Details
- Numbers: `tabular-nums` on numeric cells.
- Primary name in a row: `fw-semibold`.
- Secondary text: `rd-text-muted` or `small rd-text-muted`.
- No data: `<div class="empty-state my-2">...</div>` inside `<td colspan="...">`.

### Not allowed
- `table table-sm` without `rd-table-modern` on new management pages.
- Bare tables without an `rd-card` wrapper.

**Reference:** `templates/sales/partials/management_sale_list_results.html`, `templates/reports/partials/sales_report_results.html`

---

## 6. Filter bar

### Simple pattern (always visible)
```html
<div class="rd-card mb-3">
  <div class="rd-card-body rd-filter-bar">
    <form method="get" class="row g-3 align-items-end">
      <div class="col-md-4">
        <label class="form-label" for="...">...</label>
        <input class="form-control form-control-sm" ...>
      </div>
      <div class="col-12 d-flex flex-wrap gap-2">
        <button type="submit" class="btn btn-primary btn-sm">Apply</button>
        <a class="btn btn-outline-secondary btn-sm" href="...">Reset</a>
      </div>
    </form>
  </div>
</div>
```

### Collapsible pattern (HTMX / many filters)
Use `templates/partials/filter_card_open.html` + `filter_card_close.html`.

**Reference:** `templates/companies/company_list.html`, `templates/sales/management_sale_list.html`

---

## 7. Forms and buttons

### Form fields (Django)
In `forms.py` always use:
```python
widget=forms.TextInput(attrs={"class": "form-control"})
widget=forms.Select(attrs={"class": "form-select"})
```

### ON/OFF switches
```html
<div class="form-check form-switch">
  {{ form.field }}
  <label class="form-check-label fw-semibold" for="...">...</label>
</div>
<p class="small text-secondary mb-0">Explain the effect.</p>
```

### Buttons
| Type | Class |
|--------|--------|
| Primary action | `btn btn-primary` |
| Secondary action | `btn btn-outline-secondary` |
| Danger | `btn btn-outline-danger` or `btn btn-danger` |
| Small, inside a table | `btn btn-sm btn-outline-secondary` |

---

## 8. Badges

```html
<span class="rd-badge rd-badge--pending">...</span>
<span class="rd-badge rd-badge--paid">...</span>
<span class="rd-badge rd-badge--neutral">...</span>
```

Do not use Bootstrap's `badge bg-*` directly in new management screens.

---

## 9. Typography

| Class | Usage |
|--------|-----------|
| `rd-heading-xl` | Page title (H1) |
| `rd-heading-lg` | Section title inside a card |
| `rd-text-muted` | Description, hint, secondary text |
| `rd-label` | KPI / invoice labels |

---

## 10. Employee screen

- Template: `base_employee.html`
- Content lives inside `rd-employee-main`
- Sales forms: `rd-sale-form`, `rd-field-group`, `rd-field-label`
- Do **not** use the full management layout (sidebar) on the employee screen.

---

## 11. Colors and theme

- Theme: `data-bs-theme="light|dark"` on `<html>`.
- Primary color: `--rd-accent` / `--bs-primary` (indigo).
- Do **not** hard-code hex colors in templates — use CSS variables or the KPI classes:
  - `kpi-success`, `kpi-danger`, `kpi-warning`, `kpi-info`

---

## 12. RTL / Arabic

- `dir="rtl"` and `lang="ar"` are set by Django i18n.
- Use `margin-inline-*`, `padding-inline-*`, `text-start`/`text-end` — no `ml-*`/`mr-*` in new CSS.
- Arabic font: `--rd-font-ar` (Cairo) is applied automatically on `html[lang="ar"]`.

---

## 13. Golden references

Copy from these pages when building anything new:

| Page | Path | What to copy |
|--------|--------|-----------|
| Company details | `templates/companies/company_detail.html` | Tabs + section cards |
| Sales list | `templates/sales/management_sale_list.html` | Datagrid table |
| Companies list | `templates/companies/company_list.html` | Filters + table |
| Employee details | `templates/employees/employee_detail.html` | Tabs + filters + tables |
| System settings | `templates/core/system_settings.html` | Switches form in a card |
| Dashboard | `templates/reports/dashboard.html` | KPIs + charts |

---

## 14. Anti-patterns

1. **Pill tabs** for app sections → use `nav-tabs rd-section-tabs`.
2. **Raw Bootstrap tables** without `rd-table-modern` + `rd-card`.
3. **Inline colors/shadows** → tokens in design-system.
4. **Bootstrap cards** (`card card-body`) on new pages → `rd-card`.
5. **Separate mobile-first design** without a desktop review — use `rd-table-dual` + mobile cards where available.
6. **External UI libraries** (Tailwind, Material, …) — not allowed.
7. **Per-page CSS** in `<style>` — consolidate into design-system or app.css with a clear reason.

---

## 15. Adding a new component

1. Search `design-system.css` — does a ready-made class exist?
2. Copy the HTML structure from a reference page (section 13).
3. If you need a shared class → add it to `design-system.css` with a short comment.
4. Update this file (`docs/DESIGN_GUIDE.md`) with one line pointing to the new component.
5. Do not create a third "variant" of the same idea (e.g. a new tab style).

---

## 16. Pre-merge checklist

- [ ] `rd-page-header` + title + description
- [ ] `rd-section-tabs` tabs, if any
- [ ] `rd-card` / `rd-card-body` cards
- [ ] `rd-table-modern` tables inside `rd-datagrid`
- [ ] `rd-filter-bar` filters
- [ ] Buttons from the buttons table (section 7)
- [ ] Empty state when there is no data
- [ ] Works in light + dark
- [ ] Works in RTL (Arabic)

---

*Last update: aligned management screens on `rd-section-tabs` tabs, datagrid tables and `rd-card` cards.*
