"""
Application configuration for Smart Automated Closet System.

This file centralizes tunable parameters so that porting to different
hardware (e.g., different stepper motor, different GPIO pins) only
requires edits here instead of scattered magic numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class AppConfig:
    """
    Strongly typed configuration object.

    This could be extended to read environment variables (.env) if needed.
    """

    # Database configuration
    database_path: Path = field(
        default_factory=lambda: Path("database") / "smart_closet.sqlite3"
    )

    # Camera configuration
    camera_index: int = 0  # default USB camera index

    # Carousel and motor configuration
    carousel_slots: int = 40
    motor_steps_per_rev: int = 200  # typical stepper: 1.8 degrees/step -> 200 steps

    # GPIO pin mapping for A4988 + stepper motor.
    #
    # GPIO PIN MAPPING TABLE (BCM numbering)
    # --------------------------------------
    # +-----------+-------------+-----------------------------+
    # | Signal    | GPIO Pin    | Description                 |
    # +-----------+-------------+-----------------------------+
    # | STEP      | 17          | Step pulse input            |
    # | DIR       | 27          | Direction input             |
    # | ENABLE    | 22          | Enable (LOW = enabled)      |
    # | MS1/MS2   | (optional)  | Microstepping (not used)    |
    # | GND/VMS   | -           | Power (wired externally)    |
    # +-----------+-------------+-----------------------------+
    #
    # NOTE: These are safe defaults; modify to match your wiring.
    motor_pins: Dict[str, int] = field(
        default_factory=lambda: {"STEP": 17, "DIR": 27, "ENABLE": 22}
    )

    # Motor timing configuration
    step_delay_seconds: float = 0.002  # delay between step pulses

