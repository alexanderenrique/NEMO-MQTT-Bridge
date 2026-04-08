from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("NEMO_mqtt_bridge", "0002_mqtt_eventqueue_mqttbridgestatus"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="mqttconfiguration",
            constraint=models.UniqueConstraint(
                fields=("enabled",),
                condition=Q(enabled=True),
                name="nemo_mqtt_unique_enabled_configuration",
            ),
        ),
    ]

