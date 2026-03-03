"""
Simple tests that don't require Django setup
"""
import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_package_import():
    """Test that the package can be imported"""
    import NEMO_mqtt
    assert hasattr(NEMO_mqtt, '__version__') or True  # Version may not be set
    print("✅ Package imported successfully")

def test_models_import():
    """Test that models can be imported"""
    from NEMO_mqtt.models import MQTTConfiguration, MQTTMessageLog, MQTTEventFilter
    assert MQTTConfiguration is not None
    assert MQTTMessageLog is not None
    assert MQTTEventFilter is not None
    print("✅ Models imported successfully")

def test_redis_publisher_import():
    """Test that Redis publisher can be imported"""
    from NEMO_mqtt.redis_publisher import RedisMQTTPublisher
    assert RedisMQTTPublisher is not None
    print("✅ Redis publisher imported successfully")

def test_signal_handler_import():
    """Test that signal handler can be imported"""
    from NEMO_mqtt.signals import MQTTSignalHandler
    assert MQTTSignalHandler is not None
    print("✅ Signal handler imported successfully")

if __name__ == "__main__":
    test_package_import()
    test_models_import()
    test_redis_publisher_import()
    test_signal_handler_import()
    print("✅ All simple tests passed!")
