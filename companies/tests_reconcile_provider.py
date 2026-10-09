from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase

from companies.forms import CompanyForm, ProductLineForm


class ReconcileProviderFormTests(SimpleTestCase):
    def test_reconcile_provider_choices(self):
        choices = [c[0] for c in CompanyForm().fields["reconcile_provider"].choices]
        self.assertEqual(choices, ["", "sky", "layan"])

    def test_product_line_form_has_no_unit_cost(self):
        self.assertNotIn("estimated_unit_cost", ProductLineForm().fields)


class ReconcileProviderMigrationTests(TransactionTestCase):
    """companies/0008 maps refresh-only providers to "" while renaming the field."""

    before = [("companies", "0007_sim_phase3_4")]
    after = [("companies", "0008_reconcile_provider_and_drop_unit_cost")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_areen_and_aloha_become_empty(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old_apps = executor.loader.project_state(self.before).apps
        OldCompany = old_apps.get_model("companies", "Company")
        ids = {
            provider: OldCompany.objects.create(
                name=f"{provider or 'none'} co", phone_refresh_provider=provider
            ).pk
            for provider in ("sky", "layan", "areen", "aloha", "")
        }

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.after)
        new_apps = executor.loader.project_state(self.after).apps
        Company = new_apps.get_model("companies", "Company")

        providers = dict(Company.objects.values_list("pk", "reconcile_provider"))
        self.assertEqual(
            {name: providers[pk] for name, pk in ids.items()},
            {"sky": "sky", "layan": "layan", "areen": "", "aloha": "", "": ""},
        )
