from django.db import migrations

REMOVED_APPS = ("employees",)

# FK columns into the removed app. Earlier migrations no longer create them,
# so they only exist on databases migrated before the app was removed.
STALE_COLUMNS = (
    ("sales", "Sale", "employee_recipient_id"),
    ("customers", "CustomerPayment", "employee_recipient_id"),
    ("customers", "CustomerPaymentSubmission", "employee_recipient_id"),
)

# Children before parents so FK constraints never block a drop.
REMOVED_TABLES = (
    "employees_employeeledgerentry",
    "employees_employeeprofile",
)


def _column_exists(connection, table, column):
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
    return any(col.name == column for col in description)


def drop_employees_app(apps, schema_editor):
    connection = schema_editor.connection
    qn = schema_editor.quote_name

    for app_label, model_name, column in STALE_COLUMNS:
        model = apps.get_model(app_label, model_name)
        table = model._meta.db_table
        if not _column_exists(connection, table, column):
            continue
        if connection.vendor == "sqlite":
            # SQLite cannot drop an FK column in place; rebuilding the table
            # from the model state copies every column except the stale one.
            schema_editor._remake_table(model)
        else:
            schema_editor.execute(f"ALTER TABLE {qn(table)} DROP COLUMN {qn(column)} CASCADE")

    cascade = " CASCADE" if connection.vendor == "postgresql" else ""
    for table in REMOVED_TABLES:
        schema_editor.execute(f"DROP TABLE IF EXISTS {qn(table)}{cascade}")

    placeholders = ", ".join(["%s"] * len(REMOVED_APPS))
    stale_ct = f"SELECT id FROM django_content_type WHERE app_label IN ({placeholders})"
    stale_perm = f"SELECT id FROM auth_permission WHERE content_type_id IN ({stale_ct})"
    for sql in (
        f"DELETE FROM auth_user_user_permissions WHERE permission_id IN ({stale_perm})",
        f"DELETE FROM auth_group_permissions WHERE permission_id IN ({stale_perm})",
        f"DELETE FROM auth_permission WHERE content_type_id IN ({stale_ct})",
        f"UPDATE django_admin_log SET content_type_id = NULL WHERE content_type_id IN ({stale_ct})",
        f"DELETE FROM django_content_type WHERE app_label IN ({placeholders})",
        f"DELETE FROM django_migrations WHERE app IN ({placeholders})",
    ):
        schema_editor.execute(sql, list(REMOVED_APPS))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_drop_removed_app_tables"),
        ("sales", "0017_remove_employee_payment"),
        ("customers", "0007_remove_employee_payment"),
        ("expenses", "0002_expense_expense_date_desc_idx_and_more"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="appsettings",
            name="sales_show_employee_payment",
        ),
        migrations.RunPython(drop_employees_app, migrations.RunPython.noop),
    ]
