"""Shared test setup."""
import os

# Tests must never add tasks to this computer's real scheduler (Task Scheduler, launchd, systemd, cron).
os.environ["INPACE_SCHEDULER"] = "off"
