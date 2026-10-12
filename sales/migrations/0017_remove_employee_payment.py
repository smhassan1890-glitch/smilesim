from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0016_payment_recipients"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="sale",
            name="paid_via_employee",
        ),
    ]
