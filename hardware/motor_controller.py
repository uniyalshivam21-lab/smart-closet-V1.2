"""
Safe GPIO control logic for stepper motor via A4988 driver.

This module is responsible for:
- Abstracting away low-level GPIO.
- Providing a simple API: rotate_to_slot(target_slot).
- Ensuring safe enabling/disabling of the motor driver.

UML (textual):
--------------
Class StepperMotorController
    - steps_per_revolution: int
    - slots: int
    - gpio_pins: dict
    - current_slot: int
    + rotate_to_slot(target_slot: int) -> None
    + _step(direction: int, steps: int) -> None

Class MockStepperMotorController
    (implements same API but logs instead of touching GPIO)

Flowchart (rotate_to_slot):
---------------------------
START
  -> compute steps_per_slot
  -> compute delta = (target - current) mod slots
  -> compute direction & step_count (shortest path)
  -> enable driver
  -> pulse STEP pin step_count times
  -> disable driver
  -> update current_slot
  -> END
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict

try:
    import RPi.GPIO as GPIO  # type: ignore[import]
except ImportError:  # pragma: no cover - not available on non-RPi
    GPIO = None  # type: ignore[assignment]


@dataclass
class StepperMotorController:
    """
    Real GPIO-based motor controller.

    NOTE: This class assumes it is running on a Raspberry Pi with RPi.GPIO
    library installed and the pins wired safely through an A4988 driver.
    """

    steps_per_revolution: int
    slots: int
    gpio_pins: Dict[str, int]
    step_delay_seconds: float = 0.002
    current_slot: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if GPIO is None:
            raise RuntimeError("RPi.GPIO is not available; cannot use real controller.")

        self._logger = logging.getLogger(self.__class__.__name__)
        GPIO.setmode(GPIO.BCM)

        self._step_pin = self.gpio_pins["STEP"]
        self._dir_pin = self.gpio_pins["DIR"]
        self._enable_pin = self.gpio_pins["ENABLE"]

        GPIO.setup(self._step_pin, GPIO.OUT)
        GPIO.setup(self._dir_pin, GPIO.OUT)
        GPIO.setup(self._enable_pin, GPIO.OUT)

        # Disable by default (HIGH on A4988 usually disables)
        GPIO.output(self._enable_pin, GPIO.HIGH)

    def _enable(self) -> None:
        GPIO.output(self._enable_pin, GPIO.LOW)  # LOW = enabled

    def _disable(self) -> None:
        GPIO.output(self._enable_pin, GPIO.HIGH)

    def _perform_steps(self, direction_cw: bool, steps: int) -> None:
        """
        Low-level stepping routine.
        """
        GPIO.output(self._dir_pin, GPIO.HIGH if direction_cw else GPIO.LOW)
        self._enable()

        for _ in range(steps):
            GPIO.output(self._step_pin, GPIO.HIGH)
            time.sleep(self.step_delay_seconds)
            GPIO.output(self._step_pin, GPIO.LOW)
            time.sleep(self.step_delay_seconds)

        self._disable()

    def rotate_to_slot(self, target_slot: int) -> None:
        """
        Rotate the carousel to align a specific slot with the pickup point.

        Assumptions:
        -----------
        - Slot 0 corresponds to the current pickup alignment at boot time.
          (In practice, you should home the carousel using a limit switch.)
        - Slots are evenly spaced around the circle.
        """
        if not (0 <= target_slot < self.slots):
            raise ValueError(f"target_slot must be in [0, {self.slots}), got {target_slot}")

        steps_per_slot = self.steps_per_revolution // self.slots
        delta = (target_slot - self.current_slot) % self.slots

        # Choose shortest rotation direction
        if delta > self.slots / 2:
            # Rotate counter-clockwise
            steps = int((self.slots - delta) * steps_per_slot)
            direction_cw = False
        else:
            # Rotate clockwise
            steps = int(delta * steps_per_slot)
            direction_cw = True

        self._logger.info(
            "Rotating from slot %d to slot %d: steps=%d, direction_cw=%s",
            self.current_slot,
            target_slot,
            steps,
            direction_cw,
        )

        self._perform_steps(direction_cw=direction_cw, steps=steps)
        self.current_slot = target_slot


@dataclass
class MockStepperMotorController:
    """
    Mock motor controller for development on non-Raspberry Pi systems.

    Instead of toggling GPIO, we log the intended motion. This makes the
    rest of the backend fully runnable on laptops or desktops.
    """

    steps_per_revolution: int
    slots: int
    current_slot: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)

    def rotate_to_slot(self, target_slot: int) -> None:
        if not (0 <= target_slot < self.slots):
            raise ValueError(f"target_slot must be in [0, {self.slots}), got {target_slot}")

        steps_per_slot = self.steps_per_revolution // self.slots
        delta = (target_slot - self.current_slot) % self.slots
        if delta > self.slots / 2:
            steps = int((self.slots - delta) * steps_per_slot)
            direction = "CCW"
        else:
            steps = int(delta * steps_per_slot)
            direction = "CW"

        self._logger.info(
            "[MOCK] Rotating from slot %d to %d: %d steps (%s)",
            self.current_slot,
            target_slot,
            steps,
            direction,
        )
        self.current_slot = target_slot

