"""core/0008 drops tables and bookkeeping rows left by removed apps."""
from __future__ import annotations

import importlib

from django.apps import apps as global_apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase

migration = importlib.import_module("core.migrations.0008_drop_removed_app_tables")


def _tables():
    with connection.cursor() as cursor:
        return set(connection.introspection.table_names(cursor))


class DropRemovedAppTablesTests(TestCase):
    def setUp(self):
        editor = connection.schema_editor()
        editor.execute("CREATE TABLE phone_refresh_refreshlog (id integer PRIMARY KEY)")
        editor.execute("CREATE TABLE inventory_simcard (id integer PRIMARY KEY)")
        self.ct = ContentType.objects.create(app_label="inventory", model="simcard")
        Permission.objects.create(content_type=self.ct, codename="view_simcard", name="Can view")
        MigrationRecorder.Migration.objects.create(app="inventory", name="0001_initial")
        self.kept_ct = ContentType.objects.get_for_model(Permission)

    def test_drops_tables_and_bookkeeping_rows(self):
        migration.drop_removed_app_tables(global_apps, connection.schema_editor())

        tables = _tables()
        self.assertNotIn("phone_refresh_refreshlog", tables)
        self.assertNotIn("inventory_simcard", tables)
        self.assertFalse(ContentType.objects.filter(app_label__in=migration.REMOVED_APPS).exists())
        self.assertFalse(Permission.objects.filter(content_type_id=self.ct.pk).exists())
        self.assertFalse(
            MigrationRecorder.Migration.objects.filter(app__in=migration.REMOVED_APPS).exists()
        )
        self.assertTrue(ContentType.objects.filter(pk=self.kept_ct.pk).exists())

    def test_is_a_noop_when_nothing_is_left(self):
        migration.drop_removed_app_tables(global_apps, connection.schema_editor())
        migration.drop_removed_app_tables(global_apps, connection.schema_editor())
        self.assertNotIn("inventory_simcard", _tables())

    def test_removed_tables_cover_every_removed_app(self):
        prefixes = {t.split("_", 1)[0] for t in migration.REMOVED_TABLES}
        self.assertEqual(prefixes, {"phone", "sms", "inventory"})
        self.assertEqual(len(migration.REMOVED_TABLES), len(set(migration.REMOVED_TABLES)))
