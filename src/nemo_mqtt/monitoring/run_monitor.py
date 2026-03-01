#!/usr/bin/env python3
"""
MQTT Monitoring Runner
This script provides an easy way to run the MQTT monitoring tools with proper environment setup.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def find_venv():
    """Find the virtual environment"""
    cwd = Path.cwd()
    possible_paths = [
        cwd / "venv",
        cwd / ".venv",
        Path.home() / ".virtualenvs" / "nemo-ce",
    ]

    for venv_path in possible_paths:
        if venv_path.exists() and (venv_path / "bin" / "python").exists():
            return venv_path

    return None


def get_python_executable():
    """Get the Python executable to use"""
    venv_path = find_venv()
    if venv_path:
        return str(venv_path / "bin" / "python")
    else:
        # Fall back to system Python
        return sys.executable


def run_script(script_name, args=None):
    """Run a monitoring script with proper environment"""
    script_dir = Path(__file__).parent
    script_path = script_dir / script_name

    if not script_path.exists():
        print(f"[ERROR] Script not found: {script_path}")
        return False

    python_exe = get_python_executable()

    # Prepare command
    cmd = [python_exe, str(script_path)]
    if args:
        cmd.extend(args)

    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, cwd=Path.cwd())
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return True
    except Exception as e:
        print(f"[ERROR] Error running script: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="MQTT Monitoring Tools")
    parser.add_argument(
        "tool",
        choices=["mqtt", "redis", "test"],
        help="Monitoring tool to run: mqtt (full monitor), redis (redis only), test (test signals)",
    )
    parser.add_argument(
        "--args", nargs="*", help="Additional arguments to pass to the tool"
    )

    args = parser.parse_args()

    print("MQTT Plugin Monitoring Tools")
    print("=" * 40)

    # Check if we're in the right directory
    if not (Path.cwd() / "manage.py").exists():
        print("[ERROR] Please run this script from the NEMO project root directory")
        return 1

    # Find and display Python environment
    venv_path = find_venv()
    if venv_path:
        print(f"[OK] Using virtual environment: {venv_path}")
    else:
        print("WARNING: No virtual environment found, using system Python")

    print(f"Python executable: {get_python_executable()}")
    print()

    # Run the appropriate tool
    if args.tool == "mqtt":
        success = run_script("mqtt_monitor.py", args.args)
    elif args.tool == "redis":
        success = run_script("redis_checker.py", args.args)
    elif args.tool == "test":
        python_exe = get_python_executable()
        cmd = [python_exe, "manage.py", "test_mqtt_api"]
        if args.args:
            cmd.extend(args.args)
        print(f"Running: {' '.join(cmd)}")
        print("=" * 60)
        try:
            result = subprocess.run(cmd, cwd=Path.cwd())
            success = result.returncode == 0
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            success = True
        except Exception as e:
            print(f"[ERROR] Error: {e}")
            success = False
    else:
        print(f"[ERROR] Unknown tool: {args.tool}")
        return 1

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
