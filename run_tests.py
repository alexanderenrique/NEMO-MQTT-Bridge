#!/usr/bin/env python
"""Run tests via pytest. Use: python run_tests.py or pytest"""
import os
import sys

# Prefer src layout: add src to path so NEMO_mqtt is importable without pip install -e .
_root = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(_root, "src")
if os.path.isdir(_src) and _src not in sys.path:
    sys.path.insert(0, _src)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.test_settings')

if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main(['-v', '--tb=short'] + sys.argv[1:]))
