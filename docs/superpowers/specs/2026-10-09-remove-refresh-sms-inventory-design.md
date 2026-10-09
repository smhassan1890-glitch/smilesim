# Remove phone refresh, SMS gateway, and SIM inventory — Design

**Date:** 2026-10-09  
**Status:** Design approved in chat; awaiting written-spec review

## Problem

Three features are no longer wanted and must be removed from the project completely — code, UI, data, and every dependency in other apps:

| Sidebar entry | Django app | Also includes |
|---------------|------------|---------------|
| Update link | `phone_refresh` | Public refresh page on `rn.prosim.ps`, providers, API tokens, reports, subdomain middleware |
| Messages update | `sms_gateway` | Device API, Android app in `android_gateway/`, its CI workflow |
| Operations → SIM inventory | `inventory` | "New SIM" option on sales entry, SIM consumption on approve/cancel/payment |

The "Operations" sidebar group stays (Sales, Expenses); only its SIM inventory link is removed.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Sky report matching (`companies/sky_reconcile.py`) | **Keep.** Move the Sky Sales portal client out of `phone_refresh` into `companies`, stripped of refresh-only code |
| "New SIM" on sales | **Remove entirely**: checkbox, serial/ICCID, badge, and `Sale` fields |
| Production tables | **Drop** via migration (back up first) |
| Removal strategy | **Full removal in one release**: delete app folders entirely, edit the one historical migration that depends on `inventory` |
| `ProductLine.estimated_unit_cost` | **Remove** (only read by inventory valuation) |
| `Company.phone_refresh_provider` | **Rename** to `reconcile_provider`; choices reduced to Not set / Sky / Layan |
| `sky_lab/` | **Delete** (refresh experiments) |
| Verification DBs | SQLite **and** a local PostgreSQL |

## Scope

### Deleted

- `phone_refresh/`, `sms_gateway/`, `inventory/` (whole packages, including migrations and tests)
- `templates/inventory/`, `templates/sms_gateway/`
- `static/phone_refresh/` (after moving the favicon), `static/js/inventory-actions.js`, `static/js/inventory-serials-paste.js`
- `templates/partials/sale_new_sim_badge.html` and its usages
- `android_gateway/`, `.github/workflows/android.yml`
- `sky_lab/`
- `jsonpath-ng` from `requirements.txt`

### Moved

- `phone_refresh/providers/sky_sales_client.py` → `companies/sky_sales_client.py`. Keep: session dataclass, errors, proxy helpers, login + OTP, session file load/save, report fetch used by reconcile (`GetEot4RReportData`), env/TOTP helpers, `client_from_env`. Drop: refresh response helpers, subscriber search / costs / task creation, `execute_refresh`.
- Sky client session/login tests from `phone_refresh/tests_sky_sales_client.py` → `companies/tests_sky_sales_client.py`; the session-file test uses `tempfile` instead of a hard-coded `/tmp` path.
- `static/phone_refresh/img/favicon.png` → `static/img/favicon.png`; update `templates/partials/favicon.html`.

### Modified

- **Settings / routing:** remove the three apps from `INSTALLED_APPS`, their includes from `config/urls.py` (including `sms_gateway.api_urls`), and `PhoneRefreshSubdomainMiddleware`. Remove the `rn.prosim.ps` public-page bypass from `core/middleware.py`. Remove the stale `phone_refresh` comment in `config/settings/production.py`.
- **Sidebar** (`templates/partials/management_nav.html`): remove the Update link and Messages update groups, the SIM inventory link, and their `ns` checks in the active-section/open-state conditions.
- **Employee sales entry** (`sales/views/employee.py`, `sales/forms.py`, `sales/urls.py`, `sales/views/__init__.py`, `templates/sales/employee_entry.html`): remove refresh-number button and endpoint, "last refresh" display, New SIM checkbox + serial field, SIM stock preview endpoint.
- **Sales services** (`sales/services.py`): remove `is_new_sim` / serial parameters, SIM consumption on approval, SIM reversal on cancel (both call sites).
- **Customers:** remove SIM consumption in `customers/services.py` (both call sites) and the SIM balance card in `customers/views/crud.py` + `templates/customers/customer_detail.html`.
- **AppSettings** (`core/models.py`, `core/forms.py`, `templates/core/_system_settings_general.html`): remove `sales_inventory_enabled`, `sales_show_refresh_phone`, `public_default_language`, `public_default_theme`.
- **Companies:** rename `phone_refresh_provider` → `reconcile_provider` (model, form, `layan_reconcile.py`, `sky_reconcile.py`, `views.py`, `templates/companies/company_detail.html`); remove `estimated_unit_cost` (model, form). Update imports of the Sky client.
- **Tests in remaining apps:** drop/adjust tests that import removed models (`sales/tests.py`, `customers/tests.py`, `core/tests*.py`, `companies/tests*.py`).
- **Translations:** remove obsolete keys from `tools/fill_ar_translations.py`; regenerate `locale/ar/LC_MESSAGES/django.po` with `makemessages --no-obsolete`, re-run the fill script, `compilemessages` (requires installing gettext on this machine).
- **Docs/config:** `README.md`, `DEPLOY_COOLIFY.md`, `.env.example` (drop `rn.prosim.ps`), `docs/DESIGN_GUIDE.md` (replace references to removed templates). `docs/superpowers/` history is left as-is.

## Database and migrations

Order matters; each step depends on the previous one.

1. **Edit `sales/migrations/0012_sale_is_new_sim_sale_sim_consumed_at_and_more.py`:** remove the `('inventory', '0001_initial')` dependency and the `AddField` for `sim_stock_movement`. Required so the migration graph loads without the `inventory` app.
2. **New `sales/migrations/0015_...`:** `RemoveField` for `is_new_sim`, `sim_serial_or_iccid`, `sim_consumed_at`. Plus a custom operation that, only if the column `sales_sale.sim_stock_movement_id` exists (old databases), removes it through Django's schema editor using a stand-in field, so SQLite rebuilds the table and PostgreSQL drops the column with its FK constraint. State is unaffected (the field no longer exists in state after step 1).
3. **New `companies/migrations/0008_...`:** `RemoveField estimated_unit_cost`; `RenameField phone_refresh_provider → reconcile_provider`; `AlterField` with the new label/choices; data step mapping `areen` / `aloha` to empty.
4. **New `core/migrations/0007_...`** (depends on step 2): remove the four `AppSettings` fields, then a `RunPython` that:
   - Drops each table of the removed apps if it exists, children before parents (`CASCADE` on PostgreSQL):  
     `sms_gateway_outboundsms`, `sms_gateway_inboundsms`, `sms_gateway_smsaccessrule`, `sms_gateway_smsreplypolicy`, `sms_gateway_smsgatewaydevice`, `sms_gateway_smsgatewaysettings`,  
     `phone_refresh_refreshlog`, `phone_refresh_providerresponserule`, `phone_refresh_customermessage`, `phone_refresh_sitesettings`, `phone_refresh_apitoken`, `phone_refresh_apisettings`, `phone_refresh_systemsettings`, `phone_refresh_providerconfig`, `phone_refresh_refreshstatus`,  
     `inventory_simcard`, `inventory_simstockmovement`, `inventory_simstockbalance`.
   - Deletes `django_migrations` rows for `phone_refresh`, `sms_gateway`, `inventory`, and their `ContentType` rows (cascading to permissions and admin log entries).
   - Is irreversible.

On a fresh database none of these tables exist, so the drop step is a no-op.

**Deploy note:** run `scripts/backup_postgres.sh` (or `pg_dump -Fc`) before `migrate`. Remove `rn.prosim.ps` from `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` and DNS/proxy afterwards.

## Verification

- `manage.py check` and `manage.py makemigrations --check --dry-run` clean.
- Full test suite passes on SQLite (baseline before change: 418 tests, 2 Windows-only errors; the `/tmp` one is fixed by the move).
- Migrate a copy of the current local SQLite DB (has old tables + seed data): removed tables and `sim_stock_movement_id` gone; sales/customers/companies row counts unchanged.
- Migrate from zero on empty SQLite.
- Local PostgreSQL: migrate from zero **at the pre-change commit**, seed demo data, switch to the new code, migrate, verify as above; run the test suite against it.
- Repo-wide search for `phone_refresh`, `sms_gateway`, `inventory`, `is_new_sim`, `sim_stock`, `refresh_phone`, `estimated_unit_cost`, `rn.prosim` returns nothing outside historical migrations and `docs/superpowers/`.
- Manual smoke test on runserver: sidebar, employee sale create → admin approve → cancel, customer detail, system settings, company edit, Sky reconcile page loads.

## Out of scope

- Any redesign of remaining screens.
- Changes to Layan/Sky reconcile logic beyond the import path and the provider field rename.
