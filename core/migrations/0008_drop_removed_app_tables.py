from django.db import migrations

REMOVED_APPS = ("phone_refresh", "sms_gateway", "inventory")

# Children before parents so FK constraints never block a drop.
REMOVED_TABLES = (
    "sms_gateway_outboundsms",
    "sms_gateway_inboundsms",
    "sms_gateway_smsaccessrule",
    "sms_gateway_smsreplypolicy",
    "sms_gateway_smsgatewaydevice",
    "sms_gateway_smsgatewaysettings",
    "phone_refresh_refreshlog",
    "phone_refresh_providerresponserule",
    "phone_refresh_customermessage",
    "phone_refresh_sitesettings",
    "phone_refresh_apitoken",
    "phone_refresh_apisettings",
    "phone_refresh_systemsettings",
    "phone_refresh_providerconfig",
    "phone_refresh_refreshstatus",
    "inventory_simcard",
    "inventory_simstockmovement",
    "inventory_simstockbalance",
)


def drop_removed_app_tables(apps, schema_editor):
    qn = schema_editor.quote_name
    cascade = " CASCADE" if schema_editor.connection.vendor == "postgresql" else ""
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
        ("core", "0007_remove_refresh_inventory_settings"),
        ("sales", "0015_remove_sim_fields"),
        ("companies", "0008_reconcile_provider_and_drop_unit_cost"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]

    operations = [
        migrations.RunPython(drop_removed_app_tables, migrations.RunPython.noop),
    ]
