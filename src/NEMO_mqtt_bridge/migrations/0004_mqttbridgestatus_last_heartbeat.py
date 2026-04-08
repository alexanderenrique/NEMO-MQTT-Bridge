from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("NEMO_mqtt_bridge", "0003_unique_enabled_mqttconfiguration"),
    ]

    operations = [
        migrations.AddField(
            model_name="mqttbridgestatus",
            name="last_heartbeat",
            field=models.DateTimeField(
                blank=True,
                help_text="Set periodically by the bridge while the consumption loop runs; used for optional supervisor health checks",
                null=True,
            ),
        ),
    ]
