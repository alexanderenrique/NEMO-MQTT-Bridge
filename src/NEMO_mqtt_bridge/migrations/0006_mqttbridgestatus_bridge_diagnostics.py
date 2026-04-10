# Generated manually for bridge diagnostics shared across processes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("NEMO_mqtt_bridge", "0005_remove_mqtteventfilter"),
    ]

    operations = [
        migrations.AddField(
            model_name="mqttbridgestatus",
            name="bridge_diagnostics",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Last reload reason, applied config fingerprint, etc. (written by bridge; no secrets)",
            ),
        ),
    ]
