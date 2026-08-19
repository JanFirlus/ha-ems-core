"""Konstanten für die EMS-Core-Integration."""
from datetime import timedelta

DOMAIN = "ems_core"

CONF_HOST = "host"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

# Bekannte Leistungs-Keys in den Adapter-Detail-Dicts, gleiche Liste wie
# POWER_KEYS in ems-stack/ems-core/app/api/energyflow.py und
# static/app.js (extractPowerW) - drei Sprachen, eine Konvention.
POWER_KEYS = ("power", "apower", "current_power_w", "power_w", "leistung")
