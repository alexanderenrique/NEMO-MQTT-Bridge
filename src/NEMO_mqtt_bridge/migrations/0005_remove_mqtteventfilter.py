# Generated manually — removes per–event-type MQTT toggles (all events always published).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("NEMO_mqtt_bridge", "0004_mqttbridgestatus_last_heartbeat"),
    ]

    operations = [
        migrations.DeleteModel(
            name="MQTTEventFilter",
        ),
    ]
