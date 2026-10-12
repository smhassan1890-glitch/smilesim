from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0006_payment_recipients"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="customerpayment",
            name="paid_via_employee",
        ),
        migrations.RemoveField(
            model_name="customerpaymentsubmission",
            name="paid_via_employee",
        ),
    ]
