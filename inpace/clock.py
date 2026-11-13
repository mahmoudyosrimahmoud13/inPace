"""The person's real clock.

On a computer, Python already knows the local time zone. On a phone, Python runs inside the app
and often thinks it is in London (UTC), so a sunset could show up at lunch time. The app tells
Python the real offset twice: once when it starts (INPACE_TZ_MINUTES), and again with a tiny
cookie from every page. We set it here for the whole program, so mornings, sunsets, nights,
"early bird" and "night owl" all follow the clock on the person's wall.
"""
from __future__ import annotations

import os
import time
from datetime import datetime


def offset_now() -> int:
    """Minutes ahead of UTC that Python thinks it is right now."""
    off = datetime.now().astimezone().utcoffset()
    return int(off.total_seconds() // 60) if off else 0


def use_offset(minutes) -> bool:
    """Use this offset (minutes ahead of UTC) from now on. Returns True when something changed."""
    try:
        minutes = int(str(minutes).strip())
    except (TypeError, ValueError):
        return False
    if not -14 * 60 <= minutes <= 14 * 60 or minutes == offset_now() or not hasattr(time, "tzset"):
        return False
    sign = "-" if minutes >= 0 else "+"  # in a TZ string the sign is turned around: UTC+2 is "-02:00"
    m = abs(minutes)
    os.environ["TZ"] = f"LOCAL{sign}{m // 60:02d}:{m % 60:02d}"
    time.tzset()
    return True


def from_cookie(header: bytes | str) -> None:
    """Read the tz=<minutes> cookie the pages send, and use it."""
    if isinstance(header, bytes):
        header = header.decode("latin-1")
    for part in header.split(";"):
        k, _, val = part.strip().partition("=")
        if k == "tz":
            use_offset(val)
            return


if os.environ.get("INPACE_TZ_MINUTES"):
    use_offset(os.environ["INPACE_TZ_MINUTES"])
