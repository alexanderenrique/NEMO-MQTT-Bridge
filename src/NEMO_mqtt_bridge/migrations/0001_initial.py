# Consolidated migration for fresh installs - production schema only

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MQTTConfiguration",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Configuration name", max_length=100, unique=True
                    ),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=True, help_text="Whether this configuration is active"
                    ),
                ),
                (
                    "broker_host",
                    models.CharField(
                        default="localhost",
                        help_text="MQTT broker hostname or IP",
                        max_length=255,
                    ),
                ),
                (
                    "broker_port",
                    models.IntegerField(default=1883, help_text="MQTT broker port"),
                ),
                (
                    "keepalive",
                    models.IntegerField(
                        default=60, help_text="Keep alive interval in seconds"
                    ),
                ),
                (
                    "client_id",
                    models.CharField(
                        default="nemo-mqtt-client",
                        help_text="MQTT client ID",
                        max_length=100,
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        blank=True, help_text="MQTT username", max_length=100, null=True
                    ),
                ),
                (
                    "password",
                    models.CharField(
                        blank=True, help_text="MQTT password", max_length=100, null=True
                    ),
                ),
                (
                    "use_hmac",
                    models.BooleanField(
                        default=False,
                        help_text="Sign MQTT payloads with HMAC for authenticity and integrity",
                    ),
                ),
                (
                    "hmac_secret_key",
                    models.CharField(
                        blank=True,
                        help_text="Shared secret key for HMAC signing (keep confidential)",
                        max_length=500,
                        null=True,
                    ),
                ),
                (
                    "hmac_algorithm",
                    models.CharField(
                        default="sha256",
                        help_text="Hash algorithm for HMAC (fixed at SHA-256)",
                        max_length=20,
                    ),
                ),
                (
                    "topic_prefix",
                    models.CharField(
                        default="nemo",
                        help_text="Topic prefix for all messages",
                        max_length=100,
                    ),
                ),
                (
                    "qos_level",
                    models.IntegerField(
                        choices=[(1, "At least once")],
                        default=1,
                        help_text="Quality of Service level (fixed at 1 for reliable delivery)",
                    ),
                ),
                (
                    "retain_messages",
                    models.BooleanField(
                        default=False, help_text="Retain messages on broker"
                    ),
                ),
                (
                    "clean_session",
                    models.BooleanField(
                        default=True, help_text="Start with a clean session"
                    ),
                ),
                (
                    "auto_reconnect",
                    models.BooleanField(
                        default=True,
                        help_text="Automatically reconnect on connection loss",
                    ),
                ),
                (
                    "reconnect_delay",
                    models.IntegerField(
                        default=5,
                        help_text="Delay between reconnection attempts (seconds)",
                    ),
                ),
                (
                    "max_reconnect_attempts",
                    models.IntegerField(
                        default=10,
                        help_text="Maximum reconnection attempts (0 = unlimited)",
                    ),
                ),
                (
                    "log_messages",
                    models.BooleanField(
                        default=True, help_text="Log all MQTT messages to database"
                    ),
                ),
                (
                    "log_level",
                    models.CharField(
                        choices=[
                            ("DEBUG", "DEBUG"),
                            ("INFO", "INFO"),
                            ("WARNING", "WARNING"),
                            ("ERROR", "ERROR"),
                        ],
                        default="INFO",
                        help_text="Logging level for MQTT operations",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "MQTT Configuration",
                "verbose_name_plural": "MQTT Configurations",
                "db_table": "nemo_mqtt_mqttconfiguration",
            },
        ),
        migrations.CreateModel(
            name="MQTTMessageLog",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("topic", models.CharField(help_text="MQTT topic", max_length=500)),
                ("payload", models.TextField(help_text="Message payload")),
                (
                    "qos",
                    models.IntegerField(
                        default=0, help_text="Quality of Service level"
                    ),
                ),
                (
                    "retained",
                    models.BooleanField(
                        default=False, help_text="Whether message was retained"
                    ),
                ),
                (
                    "success",
                    models.BooleanField(
                        default=True, help_text="Whether message was sent successfully"
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True,
                        help_text="Error message if sending failed",
                        null=True,
                    ),
                ),
                (
                    "sent_at",
                    models.DateTimeField(
                        auto_now_add=True, help_text="When message was sent"
                    ),
                ),
            ],
            options={
                "verbose_name": "MQTT Message Log",
                "verbose_name_plural": "MQTT Message Logs",
                "ordering": ["-sent_at"],
                "db_table": "nemo_mqtt_mqttmessagelog",
            },
        ),
        migrations.CreateModel(
            name="MQTTEventFilter",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("tool_save", "Tool Save"),
                            ("tool_delete", "Tool Delete"),
                            ("area_save", "Area Save"),
                            ("area_delete", "Area Delete"),
                            ("reservation_save", "Reservation Save"),
                            ("reservation_delete", "Reservation Delete"),
                            ("usage_event_save", "Usage Event Save"),
                            ("area_access_save", "Area Access Save"),
                        ],
                        help_text="Type of event to filter",
                        max_length=50,
                    ),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=True, help_text="Whether this event type is enabled"
                    ),
                ),
                (
                    "topic_override",
                    models.CharField(
                        blank=True,
                        help_text="Custom topic for this event type",
                        max_length=500,
                        null=True,
                    ),
                ),
                (
                    "include_payload",
                    models.BooleanField(
                        default=True, help_text="Whether to include full payload data"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "MQTT Event Filter",
                "verbose_name_plural": "MQTT Event Filters",
                "unique_together": {("event_type",)},
                "db_table": "nemo_mqtt_mqtteventfilter",
            },
        ),
    ]
