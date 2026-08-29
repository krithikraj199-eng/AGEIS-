"""
AEGIS Ω — Time Engine

Manages simulation time independently of real time.
Supports acceleration (1 sim-day = X real-seconds),
history accumulation, and time-based queries.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List


class TimeEngine:
    """
    The simulation has its own internal clock.

    At speed 1.0:   1 sim-second = 1 real-second
    At speed 60.0:  1 sim-minute = 1 real-second
    At speed 3600:  1 sim-hour   = 1 real-second
    """

    def __init__(self, speed: float = 60.0,
                 start_time: datetime | None = None):
        self.speed = speed
        self.start_time = start_time or datetime(2026, 8, 1, 8, 0, 0)
        self.current_time = self.start_time
        self.tick_count = 0
        self.paused = False

        # History log
        self.day_log: List[Dict[str, Any]] = []
        self._day_events: Dict[int, int] = {}
        self._day_incidents: Dict[int, int] = {}

    # ──────────────────────────────────────────────────────
    # TICK
    # ──────────────────────────────────────────────────────

    def tick(self, real_elapsed_seconds: float = 1.0) -> datetime:
        """Advance simulation time by one real-time step."""
        if self.paused:
            return self.current_time

        sim_delta = timedelta(seconds=real_elapsed_seconds * self.speed)
        self.current_time += sim_delta
        self.tick_count += 1
        return self.current_time

    def advance_hours(self, hours: float) -> datetime:
        """Jump forward by N simulation hours."""
        self.current_time += timedelta(hours=hours)
        self.tick_count += 1
        return self.current_time

    def advance_days(self, days: int) -> datetime:
        """Jump forward by N simulation days."""
        for d in range(days):
            self.current_time += timedelta(days=1)
            self.tick_count += 1
            self._close_day()
        return self.current_time

    # ──────────────────────────────────────────────────────
    # QUERIES
    # ──────────────────────────────────────────────────────

    @property
    def sim_hour(self) -> int:
        return self.current_time.hour

    @property
    def sim_day(self) -> int:
        return (self.current_time - self.start_time).days + 1

    @property
    def sim_date(self) -> str:
        return self.current_time.strftime("%Y-%m-%d")

    @property
    def sim_datetime(self) -> str:
        return self.current_time.strftime("%Y-%m-%d %H:%M:%S")

    def get_state(self) -> Dict[str, Any]:
        return {
            "current_time": self.sim_datetime,
            "sim_day": self.sim_day,
            "sim_hour": self.sim_hour,
            "speed": self.speed,
            "paused": self.paused,
            "tick_count": self.tick_count,
            "start_time": self.start_time.isoformat(),
            "elapsed_sim_hours": round(
                (self.current_time - self.start_time).total_seconds() / 3600, 1
            ),
        }

    # ──────────────────────────────────────────────────────
    # CONTROLS
    # ──────────────────────────────────────────────────────

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def set_speed(self, speed: float):
        self.speed = max(0.1, min(86400, speed))

    def reset(self):
        self.current_time = self.start_time
        self.tick_count = 0
        self.paused = False

    # ──────────────────────────────────────────────────────
    # DAY LOG (for institutional history)
    # ──────────────────────────────────────────────────────

    def record_day_event(self):
        day = self.sim_day
        self._day_events[day] = self._day_events.get(day, 0) + 1

    def record_day_incident(self):
        day = self.sim_day
        self._day_incidents[day] = self._day_incidents.get(day, 0) + 1

    def _close_day(self):
        day = self.sim_day - 1
        self.day_log.append({
            "day": day,
            "date": (self.start_time + timedelta(days=day - 1)).strftime("%Y-%m-%d"),
            "events": self._day_events.get(day, 0),
            "incidents": self._day_incidents.get(day, 0),
        })

    def get_day_log(self, last_n: int = 30) -> List[Dict[str, Any]]:
        return self.day_log[-last_n:]
