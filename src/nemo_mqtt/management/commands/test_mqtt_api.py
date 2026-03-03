from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.contrib.auth.models import User
from ..views import mqtt_monitor_api
import json


class Command(BaseCommand):
    help = "Test the MQTT monitor API"

    def handle(self, *args, **options):
        self.stdout.write("Testing MQTT Monitor API...")
        self.stdout.write("-" * 50)

        # Create a test request
        factory = RequestFactory()
        request = factory.get("/mqtt/monitor/api/")

        # Get or create a test user
        user, created = User.objects.get_or_create(
            username="testuser", defaults={"is_staff": True, "is_superuser": True}
        )
        request.user = user

        try:
            # Call the API view
            response = mqtt_monitor_api(request)

            self.stdout.write(f"Status Code: {response.status_code}")
            self.stdout.write(
                f"Content Type: {response.get('Content-Type', 'Unknown')}"
            )
            self.stdout.write("-" * 50)

            # Parse the response
            if hasattr(response, "content"):
                try:
                    data = json.loads(response.content.decode("utf-8"))
                    self.stdout.write("JSON Response:")
                    self.stdout.write(json.dumps(data, indent=2))
                except json.JSONDecodeError:
                    self.stdout.write("Response is not JSON:")
                    self.stdout.write(response.content.decode("utf-8")[:500])
            else:
                self.stdout.write(f"Response: {response}")

        except Exception as e:
            self.stdout.write(f"ERROR: {e}")
            import traceback

            traceback.print_exc()
