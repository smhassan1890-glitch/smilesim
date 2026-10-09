# Remove phone refresh, SMS gateway, and SIM inventory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the `phone_refresh`, `sms_gateway`, and `inventory` apps and every dependency on them, keeping Sky reconcile working.

**Architecture:** Move the Sky Sales client into `companies`, strip each feature from the apps that consume it, delete the three packages, and rewrite the one historical migration that depends on `inventory`. A final `core` migration drops leftover tables on existing databases (no-op on fresh ones).

**Tech Stack:** Django 4.2, SQLite (dev), PostgreSQL 16 (prod; verified locally with portable binaries in `%LOCALAPPDATA%\pgsql16`).

**Spec:** `docs/superpowers/specs/2026-10-09-remove-refresh-sms-inventory-design.md`

## Global Constraints

- Python: `.venv\Scripts\python.exe`; tests: `manage.py test --parallel 1`.
- No `git commit` (no Git identity configured); each task ends with a passing test run instead.
- New migrations: `sales/0015_remove_sim_fields`, `companies/0008_reconcile_provider_and_drop_unit_cost`, `core/0007_remove_refresh_inventory_settings`, `core/0008_drop_removed_app_tables`.
- Kept `Company` field name: `reconcile_provider`; choices `("", "Not set")`, `("sky", "Sky")`, `("layan", "Layan")`; `areen`/`aloha` → `""`.
- `Sale` fields removed: `is_new_sim`, `sim_serial_or_iccid`, `sim_consumed_at`, `sim_deducted_from` (+ `SimDeductedFrom`), `sim_stock_movement`.
- `AppSettings` fields removed: `sales_inventory_enabled`, `sales_show_refresh_phone`, `public_default_language`, `public_default_theme`.

## Review Focus

- Production PostgreSQL has `sales_sale.sim_stock_movement_id` with an FK to `inventory_simstockmovement` → migrate must succeed and drop both (Task 5 PG run).
- Companies with provider `areen`/`aloha` → become `""`; `sky`/`layan` preserved (Task 2 test + Task 5 PG run).
- Bookmarked old URLs (`/inventory/`, `/phone-refresh/`, SMS device API) → 404, not 500 (Task 4 test).
- Cancelling/deleting a sale that was a "new SIM" sale before the change → works with no inventory side effects (existing sales tests, Task 4).
- Sky session file path on Windows (`/tmp` missing) → uses `tempfile.gettempdir()` (Task 1 test).

---

### Task 0: Capture pre-change databases

- [ ] Copy `db.sqlite3` → `db_before.sqlite3` (already migrated + seeded with old schema).
- [ ] Init a PG cluster (`initdb -U postgres -A trust`), start on port 5433, `createdb recharge_verify`; with `POSTGRES_DB=recharge_verify POSTGRES_PORT=5433 POSTGRES_USER=postgres` run `migrate` + `seed_demo` on the **unchanged** code. Set one company's `phone_refresh_provider='areen'`, create one `inventory` balance+movement and one sale with `sim_stock_movement` set, so the FK path is exercised.

### Task 1: Move Sky Sales client into `companies`

**Files:** Create `companies/sky_sales_client.py`, `companies/tests_sky_sales_client.py`; modify `companies/sky_reconcile.py:713`, `companies/views.py:168`.

**Interfaces — Produces:** `companies.sky_sales_client`: `SkySalesClient`, `SkySalesSession`, `SkySalesError`, `SkySalesSessionError`, `client_from_env()`, `session_file_path()`, `load_dotenv_sky()`, `resolve_otp_code()`, `has_auto_totp()`.

- [ ] Copy the client, dropping `refresh_response`, `refresh_not_updated`, `refresh_system_error`, `error_response`, `_sim_field`, `load_global_sub_customer_id`, `search_subscriber`, `_build_task_*`, `_refresh_sim_once`, `refresh_sim`, `execute_refresh`, and the `sky_lab/.env` path in `_sky_env_paths`. Default session path: `Path(tempfile.gettempdir()) / ".sky_sales_session.json"`.
- [ ] Move all tests from `phone_refresh/tests_sky_sales_client.py`, retargeting patches to `companies.sky_sales_client`, writing the session file under `tempfile.mkdtemp()`.
- [ ] Update the two imports. Run `manage.py test companies` → PASS.

### Task 2: Company provider rename + drop unit cost

**Files:** `companies/models.py`, `companies/forms.py`, `companies/layan_reconcile.py:925`, `companies/sky_reconcile.py:38`, `templates/companies/company_detail.html:11,14`, `companies/tests*.py`, new migration `companies/0008_...`.

- [ ] Test `CompanyFormTests.test_reconcile_provider_choices`: `[c[0] for c in CompanyForm().fields["reconcile_provider"].choices] == ["", "sky", "layan"]`; `"estimated_unit_cost" not in ProductLineForm().fields`.
- [ ] Migration: `RunPython` mapping `areen`/`aloha` → `""` (before rename), `RenameField`, `AlterField` (label `"reconcile provider"`, help text "Which supplier report matching applies to this company."), `RemoveField estimated_unit_cost`.
- [ ] Run `manage.py test companies` → PASS.

### Task 3: Remove phone refresh + SMS gateway

**Files:** delete `phone_refresh/`, `sms_gateway/`, `templates/sms_gateway/`, `static/phone_refresh/` (favicon → `static/img/favicon.png`), `sky_lab/`, `android_gateway/`, `.github/workflows/android.yml`. Modify `config/settings/base.py`, `config/settings/production.py:106`, `config/urls.py`, `core/middleware.py:196-210`, `core/models.py`, `core/forms.py`, `templates/core/_system_settings_general.html`, `templates/partials/favicon.html`, `templates/partials/management_nav.html`, `sales/views/employee.py`, `sales/views/__init__.py`, `sales/urls.py`, `templates/sales/employee_entry.html` (refresh button, modal, JS block ~668-860), `requirements.txt` (drop `jsonpath-ng`), tests in `sales/tests.py`, `core/tests*.py`. New migration `core/0007_remove_refresh_inventory_settings` (all four `AppSettings` fields).

- [ ] Tests: `reverse("sales:employee_refresh_phone")` raises `NoReverseMatch`; favicon test expects `/static/img/favicon.png`; system-settings POST without removed fields saves.
- [ ] Run `manage.py check` + `manage.py test` → PASS.

### Task 4: Remove SIM inventory

**Files:** delete `inventory/`, `templates/inventory/`, `static/js/inventory-*.js`, `templates/partials/sale_new_sim_badge.html` (+ its includes in 5 sales templates), inventory CSS blocks in `static/css/design-system.css`. Modify `sales/models.py`, `sales/forms.py`, `sales/services.py` (params + 3 call sites), `sales/views/employee.py` (`api_sim_stock_preview`, `is_new_sim`), `sales/views/__init__.py`, `sales/urls.py`, `templates/sales/employee_entry.html` (New SIM block, `data-sim-preview-url`, preview JS), `customers/services.py:169,451`, `customers/views/crud.py:144-171`, `templates/customers/customer_detail.html:204-231`, `templates/partials/management_nav.html`, `config/settings/base.py`, `config/urls.py`, `customers/tests.py`.

- [ ] Edit `sales/migrations/0012`: drop `('inventory', '0001_initial')` dependency and the `sim_stock_movement` `AddField`.
- [ ] `sales/0015_remove_sim_fields`: `RemoveField` ×4 + `RunPython(drop_legacy_sim_stock_movement_column, noop)` — if `sim_stock_movement_id` is in `connection.introspection.get_table_description(cursor, "sales_sale")`, call `schema_editor.remove_field(Sale, stand_in)` where `stand_in = models.IntegerField(db_index=True)` with `set_attributes_from_name("sim_stock_movement")` and `column = "sim_stock_movement_id"`.
- [ ] Tests: `self.client.get("/inventory/")` and `/phone-refresh/` → 404 for admin; customer detail renders without "SIM stock".
- [ ] Run `manage.py check`, `makemigrations --check --dry-run`, `manage.py test` → PASS.

### Task 5: Drop leftover tables + verify migrations

**Files:** `core/migrations/0008_drop_removed_app_tables.py` (depends on `core/0007`, `sales/0015`, `companies/0008`), `core/tests_drop_removed_apps.py`.

**Interfaces — Produces:** `drop_removed_app_tables(apps, schema_editor)` with module constant `REMOVED_TABLES` (order from the spec) and `REMOVED_APPS = ("phone_refresh", "sms_gateway", "inventory")`.

- [ ] Test: create `phone_refresh_refreshlog` and `inventory_simcard` via raw SQL plus a `ContentType(app_label="inventory", model="simcard")` and a `django_migrations` row for `inventory`; call the function; assert tables gone, rows gone.
- [ ] Implement: `DROP TABLE IF EXISTS <t>` (+ ` CASCADE` when `connection.vendor == "postgresql"`), then delete `django_migrations` rows and `ContentType` rows for `REMOVED_APPS`.
- [ ] Copy `db_before.sqlite3` → temp, `migrate` against it: no removed tables, no `sim_stock_movement_id`, `Sale`/`Customer`/`Company` counts unchanged. Migrate an empty SQLite from zero.
- [ ] PG: `migrate` `recharge_verify` with new code; same assertions + the `areen` company now `""`; run `manage.py test` with PG env.

### Task 6: Translations, docs, final sweep

- [ ] Remove obsolete keys from `tools/fill_ar_translations.py`; `makemessages -l ar --ignore=.venv --no-obsolete`; `python tools/fill_ar_translations.py`; `compilemessages`.
- [ ] Update `README.md`, `DEPLOY_COOLIFY.md` (drop `rn.prosim.ps`, add backup-before-migrate step), `.env.example`, `docs/DESIGN_GUIDE.md`, `DESIGN.md` line 3.
- [ ] `rg` for `phone_refresh|sms_gateway|inventory|is_new_sim|sim_stock|refresh_phone|estimated_unit_cost|rn\.prosim` outside migrations/`docs/superpowers` → none.
- [ ] Full suite; runserver smoke: sidebar, employee sale → approve → cancel, customer detail, system settings, company edit, Sky reconcile page.
