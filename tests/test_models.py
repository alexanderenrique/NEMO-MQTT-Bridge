"""
Tests for NEMO MQTT Plugin models
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from nemo_mqtt.models import MQTTConfiguration, MQTTMessageLog, MQTTEventFilter


class MQTTConfigurationModelTest(TestCase):
    """Test MQTTConfiguration model"""
    
    def test_create_mqtt_configuration(self):
        """Test creating a basic MQTT configuration"""
        config = MQTTConfiguration.objects.create(
            name='Test Config',
            enabled=True,
            broker_host='localhost',
            broker_port=1883
        )
        
        self.assertEqual(config.name, 'Test Config')
        self.assertTrue(config.enabled)
        self.assertEqual(config.broker_host, 'localhost')
        self.assertEqual(config.broker_port, 1883)
        self.assertEqual(str(config), 'Test Config (Enabled)')
    
    def test_default_values(self):
        """Test default values for MQTT configuration"""
        config = MQTTConfiguration.objects.create(name='Test')
        
        self.assertEqual(config.broker_host, 'localhost')
        self.assertEqual(config.broker_port, 1883)
        self.assertEqual(config.qos_level, 1)
        self.assertFalse(config.retain_messages)
        self.assertTrue(config.clean_session)
        self.assertTrue(config.auto_reconnect)
        self.assertEqual(config.reconnect_delay, 5)
        self.assertEqual(config.max_reconnect_attempts, 10)
        self.assertTrue(config.log_messages)
        self.assertEqual(config.log_level, 'INFO')
    
    def test_hmac_configuration(self):
        """Test HMAC configuration options"""
        config = MQTTConfiguration.objects.create(
            name='HMAC Config',
            use_hmac=True,
            hmac_secret_key='test-secret-key',
            hmac_algorithm='sha256'
        )
        
        self.assertTrue(config.use_hmac)
        self.assertEqual(config.hmac_secret_key, 'test-secret-key')
        self.assertEqual(config.hmac_algorithm, 'sha256')
    
    def test_connection_settings(self):
        """Test connection management settings"""
        config = MQTTConfiguration.objects.create(
            name='Connection Test',
            keepalive=120,
            client_id='test-client',
            username='testuser',
            password='testpass'
        )
        
        self.assertEqual(config.keepalive, 120)
        self.assertEqual(config.client_id, 'test-client')
        self.assertEqual(config.username, 'testuser')
        self.assertEqual(config.password, 'testpass')


class MQTTMessageLogModelTest(TestCase):
    """Test MQTTMessageLog model"""
    
    def test_create_message_log(self):
        """Test creating a message log entry"""
        log = MQTTMessageLog.objects.create(
            topic='nemo/tools/1/start',
            payload='{"event": "tool_usage_start"}',
            qos=1,
            retained=True,
            success=True
        )
        
        self.assertEqual(log.topic, 'nemo/tools/1/start')
        self.assertEqual(log.payload, '{"event": "tool_usage_start"}')
        self.assertEqual(log.qos, 1)
        self.assertTrue(log.retained)
        self.assertTrue(log.success)
        self.assertIsNone(log.error_message)
    
    def test_failed_message_log(self):
        """Test creating a failed message log entry"""
        log = MQTTMessageLog.objects.create(
            topic='nemo/tools/1/start',
            payload='{"event": "tool_usage_start"}',
            qos=1,
            retained=False,
            success=False,
            error_message='Connection failed'
        )
        
        self.assertFalse(log.success)
        self.assertEqual(log.error_message, 'Connection failed')
        self.assertIn('Failed', str(log))
    
    def test_message_log_ordering(self):
        """Test that message logs are ordered by sent_at descending"""
        log1 = MQTTMessageLog.objects.create(
            topic='test1',
            payload='payload1',
            success=True
        )
        log2 = MQTTMessageLog.objects.create(
            topic='test2',
            payload='payload2',
            success=True
        )
        
        logs = list(MQTTMessageLog.objects.all())
        self.assertEqual(logs[0], log2)  # Most recent first
        self.assertEqual(logs[1], log1)


class MQTTEventFilterModelTest(TestCase):
    """Test MQTTEventFilter model"""
    
    def test_create_event_filter(self):
        """Test creating an event filter"""
        filter_obj = MQTTEventFilter.objects.create(
            event_type='tool_save',
            enabled=True,
            topic_override='custom/tool/save',
            include_payload=True
        )
        
        self.assertEqual(filter_obj.event_type, 'tool_save')
        self.assertTrue(filter_obj.enabled)
        self.assertEqual(filter_obj.topic_override, 'custom/tool/save')
        self.assertTrue(filter_obj.include_payload)
        self.assertEqual(str(filter_obj), 'Tool Save (Enabled)')
    
    def test_event_filter_unique_constraint(self):
        """Test that event types must be unique"""
        MQTTEventFilter.objects.create(
            event_type='tool_save',
            enabled=True
        )
        
        with self.assertRaises(Exception):  # IntegrityError
            MQTTEventFilter.objects.create(
                event_type='tool_save',
                enabled=False
            )
    
    def test_event_type_choices(self):
        """Test that event type choices are valid"""
        valid_choices = [
            'tool_save', 'tool_delete',
            'area_save', 'area_delete',
            'reservation_save', 'reservation_delete',
            'usage_event_save', 'area_access_save'
        ]
        
        for event_type in valid_choices:
            filter_obj = MQTTEventFilter.objects.create(
                event_type=event_type,
                enabled=True
            )
            self.assertEqual(filter_obj.event_type, event_type)
    
    def test_default_values(self):
        """Test default values for event filter"""
        filter_obj = MQTTEventFilter.objects.create(
            event_type='tool_save'
        )
        
        self.assertTrue(filter_obj.enabled)
        self.assertIsNone(filter_obj.topic_override)
        self.assertTrue(filter_obj.include_payload)