"""Shared test setup."""
import os

# Tests must never add tasks to this computer's real scheduler (Task Scheduler, launchd, systemd, cron).
os.environ["INPACE_SCHEDULER"] = "off"

# The first open speaks the computer's language when no browser language is sent (v1.25.2). Tests expect English,
# whatever language this computer is set to.
os.environ["LC_ALL"] = "en_US.UTF-8"
