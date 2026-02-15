"""
Smart Automated Closet System - Flask Backend
================================================

This module exposes the HTTP API used by the touchscreen kiosk UI.

High-level UML (described in text)
----------------------------------
Class Diagram (conceptual):

    +----------------------+        +----------------------+        +--------------------------+
    | FlaskApp (app)      |        | ClothingRepository   |        | RecommenderEngine        |
    +----------------------+        +----------------------+        +--------------------------+
    | - db                 |<>----- | - db_conn           |        | - repository             |
    | - detector           |        +----------------------+        +--------------------------+
    | - recommender       |        | + add_or_update()    |        | + recommend_outfit()     |
    | - motor_controller  |        | + list_clothes()     |        +--------------------------+
    +----------------------+        | + log_usage()        |
                                    +----------------------+

    +----------------------+
    | ClothingDetector     |
    +----------------------+
    | + scan_carousel()    |
    +----------------------+

    +----------------------+
    | StepperMotorController |
    +----------------------+
    | + rotate_to_slot()   |
    +----------------------+

Sequence Diagram (scan + recommend, described):
-----------------------------------------------
1. UI calls POST /api/scan
2. FlaskApp -> ClothingDetector.scan_carousel() -> camera frames -> clothing types.
3. FlaskApp -> ClothingRepository.add_or_update() to persist each clothing item and its slot.
4. UI then calls POST /api/recommend with mood/occasion/weather/time_of_day.
5. FlaskApp -> RecommenderEngine.recommend_outfit() which queries ClothingRepository and returns (top, bottom).
6. UI shows outfit to user, then calls POST /api/confirm with YES/NO.
7. If YES: FlaskApp -> StepperMotorController.rotate_to_slot() for each selected item.

Flowchart (high level, textual):
--------------------------------
START -> /api/scan -> capture images -> detect clothing types ->
persist to DB -> wait for user preferences -> /api/recommend ->
compute outfit -> show to user -> /api/confirm? -> if YES -> rotate
carousel to bring clothes to pickup point -> END; else -> allow
re-selection or manual correction.
"""

from __future__ import annotations

import logging
from typing import Dict, Any

from flask import Flask, jsonify, request, render_template

from backend.config import AppConfig
from database.db import (
    get_connection,
    ClothingRepository,
    initialize_database,
)
from ml.detector import ClothingDetector
from ml.recommendation import RecommenderEngine
from hardware.motor_controller import StepperMotorController, MockStepperMotorController
from utils.logging_utils import configure_logging


def create_app() -> Flask:
    """
    Application factory to create and configure the Flask app.

    This pattern is production-style and test-friendly.
    """
    configure_logging()
    logger = logging.getLogger(__name__)

    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    # Load configuration
    config = AppConfig()
    app.config["SMART_CLOSET"] = config

    # Initialize DB and repositories
    conn = get_connection(config.database_path)
    initialize_database(conn)
    repository = ClothingRepository(conn)

    # Initialize ML detector (camera-based, no RFID)
    detector = ClothingDetector(camera_index=config.camera_index)

    # Initialize recommendation engine
    recommender = RecommenderEngine(repository=repository)

    # Initialize motor controller:
    # On non-RPi platforms, we automatically fall back to a mock controller
    try:
        motor_controller: StepperMotorController | MockStepperMotorController
        motor_controller = StepperMotorController(
            steps_per_revolution=config.motor_steps_per_rev,
            slots=config.carousel_slots,
            gpio_pins=config.motor_pins,
        )
        logger.info("Initialized real StepperMotorController.")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Falling back to MockStepperMotorController due to error: %s", exc
        )
        motor_controller = MockStepperMotorController(
            steps_per_revolution=config.motor_steps_per_rev,
            slots=config.carousel_slots,
        )

    # Store shared components on app for later access (also helpful in tests)
    app.repository = repository  # type: ignore[attr-defined]
    app.detector = detector      # type: ignore[attr-defined]
    app.recommender = recommender  # type: ignore[attr-defined]
    app.motor_controller = motor_controller  # type: ignore[attr-defined]

    @app.route("/")
    def index() -> str:
        """
        Render the main kiosk UI (dark themed, touch friendly).
        """
        return render_template("index.html")

    @app.post("/api/scan")
    def api_scan() -> Any:
        """
        Scan the carousel using the USB camera and detect clothing types.

        Algorithm (high level):
        -----------------------
        1. Acquire image frames from camera.
        2. For each logical carousel slot:
           a. Rotate (physically) or assume static for prototype.
           b. Crop/segment region-of-interest where clothes hang.
           c. Extract simple visual features (color histogram, edges).
           d. Run a lightweight classifier to assign clothing type.
        3. Persist/update the item in SQLite with slot index and last_seen_ts.

        Returns JSON with all detected items.
        """
        logger = logging.getLogger("api_scan")

        try:
            # For this conceptual demo we assume the camera sees the whole carousel
            detections = app.detector.scan_carousel(
                slots=app.config["SMART_CLOSET"].carousel_slots
            )

            items = []
            for slot_index, clothing_type in detections.items():
                item = app.repository.add_or_update_item(
                    slot=slot_index,
                    clothing_type=clothing_type,
                )
                items.append(item)

            logger.info("Scan completed; %d items detected.", len(items))
            return jsonify({"status": "ok", "items": items})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error during scan: %s", exc)
            return jsonify({"status": "error", "message": str(exc)}), 500

    @app.get("/api/items")
    def api_items() -> Any:
        """
        List all known clothing items from the database.
        """
        items = app.repository.list_clothes()
        return jsonify({"status": "ok", "items": items})

    @app.post("/api/recommend")
    def api_recommend() -> Any:
        """
        Generate outfit recommendation (top + bottom) based on user inputs.

        Pseudocode (Recommendation Algorithm):
        --------------------------------------
        INPUT: mood, occasion, weather, time_of_day
        DB: list of items with (slot, type, usage_count, last_worn_ts)

        1. Fetch all available clothes from DB.
        2. Score each item:
           score = base_score(type, occasion) +
                   mood_modifier(mood) +
                   weather_modifier(weather, type) +
                   recency_penalty(last_worn_ts)
        3. Select top-scoring "top" item (shirt/jacket) and
           top-scoring "bottom" item (pants/skirt).
        4. Return them as recommendation; if none available, report error.
        """
        logger = logging.getLogger("api_recommend")
        data: Dict[str, Any] = request.get_json(force=True)  # type: ignore[assignment]

        mood = data.get("mood", "neutral")
        occasion = data.get("occasion", "casual")
        weather = data.get("weather", "mild")
        time_of_day = data.get("timeOfDay", "day")

        try:
            recommendation = app.recommender.recommend_outfit(
                mood=mood,
                occasion=occasion,
                weather=weather,
                time_of_day=time_of_day,
            )
            if recommendation is None:
                return (
                    jsonify(
                        {
                            "status": "no_recommendation",
                            "message": "No suitable outfit could be found.",
                        }
                    ),
                    200,
                )

            logger.info("Recommendation computed: %s", recommendation)
            return jsonify({"status": "ok", "recommendation": recommendation})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error during recommendation: %s", exc)
            return jsonify({"status": "error", "message": str(exc)}), 500

    @app.post("/api/confirm")
    def api_confirm() -> Any:
        """
        Confirm or reject the recommended outfit.

        If confirmed (YES), this endpoint will rotate the carousel to bring
        the selected clothes to the pickup point using the stepper motor.

        Motor Control Pseudocode:
        -------------------------
        INPUT: target_slot (0..N-1), current_slot
        CONSTANTS: steps_per_rev, slots

        1. steps_per_slot = steps_per_rev / slots
        2. delta = (target_slot - current_slot) mod slots
        3. If delta > slots/2:
               direction = CCW
               steps = (slots - delta) * steps_per_slot
           else:
               direction = CW
               steps = delta * steps_per_slot
        4. For i in range(steps):
               pulse STEP pin high -> low with small delay
        5. Update current_slot.
        """
        logger = logging.getLogger("api_confirm")
        data: Dict[str, Any] = request.get_json(force=True)  # type: ignore[assignment]

        accepted = bool(data.get("accepted", False))
        selected_top = data.get("top")
        selected_bottom = data.get("bottom")

        if not accepted:
            # User rejected; no movement, but we could log feedback for future ML.
            logger.info("User rejected recommendation.")
            return jsonify({"status": "rejected"})

        if not selected_top or not selected_bottom:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Selected items not provided for confirmation.",
                    }
                ),
                400,
            )

        try:
            # Move carousel to each selected slot.
            for item in (selected_top, selected_bottom):
                slot = int(item["slot"])
                logger.info("Rotating carousel to slot %d.", slot)
                app.motor_controller.rotate_to_slot(slot)
                app.repository.log_usage(item_id=item["id"])

            return jsonify({"status": "ok"})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error while moving carousel: %s", exc)
            return jsonify({"status": "error", "message": str(exc)}), 500

    return app


if __name__ == "__main__":
    # Entry point for local development or Raspberry Pi deployment.
    application = create_app()
    # For kiosk-style usage on a local network we can bind to all interfaces.
    application.run(host="0.0.0.0", port=5000, debug=True)

