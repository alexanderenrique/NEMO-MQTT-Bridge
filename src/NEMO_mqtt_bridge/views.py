"""
Views for MQTT plugin.
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
def mqtt_monitor(request):
    """Web-based MQTT monitor: bridge status, queue samples, and message history."""
    ctx: dict = {"title": "NEMO MQTT Monitor", "config": None}
    try:
        from .monitor_context import mqtt_dashboard_context

        ctx.update(mqtt_dashboard_context())
    except Exception:
        pass
    response = render(
        request,
        "nemo_mqtt/monitor.html",
        ctx,
    )
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@login_required
def mqtt_bridge_status(request):
    """Return current bridge status from DB as JSON."""
    from .utils import mqtt_bridge_status_payload

    return JsonResponse(mqtt_bridge_status_payload())
