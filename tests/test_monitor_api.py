#!/usr/bin/env python3
"""
Test script to verify the MQTT monitor API is working
"""

import os
import sys
import django
import json
import time

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'nemo-ce'))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_dev')
django.setup()

from NEMO_mqtt.views import monitor
from NEMO_mqtt.redis_publisher import redis_publisher

def test_monitor():
    print("🧪 Testing MQTT Monitor API")
    print("=" * 50)
    
    # Test Redis connection
    print("1. Testing Redis connection...")
    if redis_publisher.is_available():
        print("   ✅ Redis is available")
    else:
        print("   ❌ Redis is not available")
        return
    
    # Test monitor status
    print("2. Testing monitor status...")
    print(f"   Monitor running: {monitor.running}")
    print(f"   Messages count: {len(monitor.messages)}")
    
    # Start monitoring
    print("3. Starting monitor...")
    monitor.start_monitoring()
    time.sleep(2)  # Give it time to connect
    print(f"   Monitor running: {monitor.running}")
    
    # Publish a test message
    print("4. Publishing test message...")
    success = redis_publisher.publish_event(
        topic="nemo/test/monitor",
        payload='{"test": "message", "timestamp": "' + str(time.time()) + '"}',
        qos=0,
        retain=False
    )
    print(f"   Message published: {success}")
    
    # Wait a bit for the message to be processed
    print("5. Waiting for message processing...")
    time.sleep(3)
    
    # Check messages
    print("6. Checking messages...")
    messages = monitor.messages
    print(f"   Total messages: {len(messages)}")
    
    if messages:
        print("   Recent messages:")
        for i, msg in enumerate(messages[-3:], 1):
            print(f"     {i}. {msg['source']} - {msg['topic']} - {msg['payload'][:50]}...")
    else:
        print("   No messages found")
    
    # Test API endpoint
    print("7. Testing API endpoint...")
    from django.test import RequestFactory
    from NEMO_mqtt.views import mqtt_monitor_api
    
    factory = RequestFactory()
    request = factory.get('/monitor/api/')
    request.user = None  # Skip auth for test
    
    try:
        response = mqtt_monitor_api(request)
        data = json.loads(response.content)
        print(f"   API response: {data['count']} messages, monitoring: {data['monitoring']}")
    except Exception as e:
        print(f"   API error: {e}")
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_monitor()
