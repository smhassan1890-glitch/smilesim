from django.db import migrations, models


def clear_refresh_only_providers(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    Company.objects.filter(phone_refresh_provider__in=["areen", "aloha"]).update(
        phone_refresh_provider=""
    )


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0007_sim_phase3_4"),
    ]

    operations = [
        migrations.RunPython(clear_refresh_only_providers, migrations.RunPython.noop),
        migrations.RenameField(
            model_name="company",
            old_name="phone_refresh_provider",
            new_name="reconcile_provider",
        ),
        migrations.AlterField(
            model_name="company",
            name="reconcile_provider",
            field=models.CharField(
                blank=True,
                choices=[("", "Not set"), ("sky", "Sky"), ("layan", "Layan")],
                help_text=(
                    "Which supplier report matching applies to this company."
                    " Leave empty to match from the company name."
                ),
                max_length=20,
                verbose_name="reconcile provider",
            ),
        ),
        migrations.RemoveField(
            model_name="productline",
            name="estimated_unit_cost",
        ),
    ]
