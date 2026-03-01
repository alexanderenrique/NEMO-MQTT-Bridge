"""
Django management command to set up NEMO integration for the MQTT plugin.

Configures NEMO settings and URLs. Use --install-package to also install the
plugin via pip (when developing or installing from source).
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Set up NEMO integration for the MQTT plugin (configures settings and URLs)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--nemo-path",
            type=str,
            help="Path to NEMO-CE installation (if not in current directory)",
        )
        parser.add_argument(
            "--backup",
            action="store_true",
            help="Create backup files before modifying",
        )
        parser.add_argument(
            "--install-package",
            action="store_true",
            help="Install the plugin via pip first (pip install -e .)",
        )

    def handle(self, *args, **options):
        nemo_path = options.get("nemo_path") or os.getcwd()
        create_backup = options.get("backup", False)
        install_package = options.get("install_package", False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Setting up NEMO MQTT Plugin integration in: {nemo_path}"
            )
        )

        if install_package:
            self._install_package()

        # Check if we're in a NEMO installation
        if not self._is_nemo_installation(nemo_path):
            raise CommandError(f"{nemo_path} does not appear to be a NEMO installation")

        success_count = 0

        # Configure settings files
        settings_files = self._find_settings_files(nemo_path)
        for settings_file in settings_files:
            if self._configure_settings_file(settings_file, create_backup):
                success_count += 1

        # Configure URLs
        if self._configure_urls(nemo_path, create_backup):
            success_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"\nSetup complete! Modified {success_count} files.")
        )

        self.stdout.write("\nNext steps:")
        self.stdout.write("1. Run migrations: python manage.py migrate nemo_mqtt")
        self.stdout.write("2. Start NEMO: python manage.py runserver")
        self.stdout.write("3. Configure MQTT at /customization/mqtt/")

    def _install_package(self):
        """Install the plugin via pip in editable mode"""
        plugin_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
        self.stdout.write("Installing Python package...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", str(plugin_dir)],
                check=True,
                capture_output=True,
            )
            self.stdout.write(self.style.SUCCESS("[OK] Package installed"))
        except subprocess.CalledProcessError as e:
            raise CommandError(
                f"pip install failed: {e.stderr.decode() if e.stderr else e}"
            )

    def _is_nemo_installation(self, path):
        """Check if the path contains a NEMO installation"""
        nemo_path = Path(path)
        return (nemo_path / "manage.py").exists() and (nemo_path / "NEMO").exists()

    def _find_settings_files(self, nemo_path):
        """Find NEMO settings files"""
        settings_files = []
        patterns = [
            "settings.py",
            "settings_dev.py",
            "settings_prod.py",
            "settings_local.py",
        ]

        for pattern in patterns:
            settings_file = Path(nemo_path) / pattern
            if settings_file.exists():
                settings_files.append(str(settings_file))

        return settings_files

    def _backup_file(self, file_path):
        """Create a backup of the file"""
        backup_path = f"{file_path}.backup"
        if not os.path.exists(backup_path):
            with open(file_path, "r") as original:
                with open(backup_path, "w") as backup:
                    backup.write(original.read())
            self.stdout.write(f"[OK] Created backup: {backup_path}")
        return backup_path

    def _configure_settings_file(self, settings_file, create_backup):
        """Configure a settings file for MQTT plugin"""
        if create_backup:
            self._backup_file(settings_file)

        with open(settings_file, "r") as f:
            content = f.read()

        modified = False

        # Add to INSTALLED_APPS
        if "'nemo_mqtt'" not in content and '"nemo_mqtt"' not in content:
            pattern = r"(INSTALLED_APPS\s*=\s*\[[^\]]*)(\]\s*$)"
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

            if match:
                new_content = (
                    content[: match.start(2)] + "    'nemo_mqtt',\n" + match.group(2)
                )
                with open(settings_file, "w") as f:
                    f.write(new_content)
                self.stdout.write(
                    f"[OK] Added nemo_mqtt to INSTALLED_APPS in {settings_file}"
                )
                modified = True
            else:
                self.stdout.write(
                    f"WARNING: Could not find INSTALLED_APPS in {settings_file}"
                )
        else:
            self.stdout.write(
                f"[OK] nemo_mqtt already in INSTALLED_APPS in {settings_file}"
            )
            modified = True

        # Add logging configuration
        if "'nemo_mqtt'" not in content or "loggers" not in content:
            if "LOGGING" in content:
                pattern = r"(\s+)(\'loggers\':\s*\{[^}]*)(\})"
                match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

                if match:
                    logger_config = """
        'nemo_mqtt': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },"""
                    new_content = (
                        content[: match.start(2)]
                        + match.group(2)
                        + logger_config
                        + content[match.start(3) :]
                    )

                    with open(settings_file, "w") as f:
                        f.write(new_content)
                    self.stdout.write(f"[OK] Added MQTT logging to {settings_file}")
                    modified = True

        return modified

    def _configure_urls(self, nemo_path, create_backup):
        """Configure NEMO URLs for MQTT plugin"""
        urls_file = Path(nemo_path) / "NEMO" / "urls.py"

        if not urls_file.exists():
            self.stdout.write(f"WARNING: Could not find NEMO/urls.py at {urls_file}")
            return False

        if create_backup:
            self._backup_file(str(urls_file))

        with open(urls_file, "r") as f:
            content = f.read()

        # Check if already added
        if "nemo_mqtt.urls" in content:
            self.stdout.write(f"[OK] MQTT URLs already added to {urls_file}")
            return True

        # Add MQTT URLs
        mqtt_urls = """
    # Add MQTT plugin URLs
    urlpatterns += [
        path("mqtt/", include("nemo_mqtt.urls")),
    ]"""

        # Find a good place to add the URLs
        lines = content.split("\n")
        if lines and lines[-1].strip() == "":
            lines = lines[:-1]

        lines.extend(mqtt_urls.split("\n"))
        new_content = "\n".join(lines)

        with open(urls_file, "w") as f:
            f.write(new_content)

        self.stdout.write(f"[OK] Added MQTT URLs to {urls_file}")
        return True
