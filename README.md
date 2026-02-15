# Smart Automated Closet System (Concept Demo)

This repository contains a **code-only concept demo** of a Smart Automated
Closet System that:

- Scans clothing on a circular carousel using a **USB camera**.
- Classifies clothing types (shirt, pants, jacket, etc.) using a
  lightweight ML pipeline based on **OpenCV** and simple heuristics.
- Stores clothing metadata and usage history in a **SQLite** database.
- Provides a **touch-friendly dark-themed kiosk UI** for a 10-inch screen.
- Drives a physical carousel via a **stepper motor + A4988** driver
  connected to a **Raspberry Pi**.

## Folder Structure

- `backend/` – Flask app, configuration
- `database/` – SQLite models and repository layer
- `ml/` – Computer vision and recommendation logic
- `hardware/` – GPIO-based stepper motor control
- `templates/` – Flask HTML templates (kiosk UI)
- `static/` – CSS/JS for the frontend
- `utils/` – Shared utilities (logging, etc.)

## Running the System (Development)

1. **Install dependencies** (ideally inside a virtual environment):

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Flask backend**:

   ```bash
   cd backend
   python app.py
   ```

3. Open a browser on the Raspberry Pi (or another machine on the LAN) to:

   ```text
   http://<raspberry-pi-ip>:5000/
   ```

   The kiosk UI is optimized for a 10-inch touch display.

## Algorithms and Diagrams (Textual)

- **UML diagrams (class & sequence)**: See the top-of-file comments in
  `backend/app.py`, `database/db.py`, `ml/detector.py`,
  `ml/recommendation.py`, and `hardware/motor_controller.py`.

- **Flowcharts**:
  - Backend request handling flows are documented in `backend/app.py`.
  - Frontend interaction flow is documented in `static/js/main.js`.

- **Pseudocode**:
  - Recommendation algorithm pseudocode is documented in
    `backend/app.py` and implemented in `ml/recommendation.py`.
  - Motor control pseudocode is documented in `backend/app.py` and
    implemented in `hardware/motor_controller.py`.

## Test Cases (Conceptual)

See inline comments and docstrings for suggested **unit tests**:

- `ml/recommendation.py` – score computation and outfit selection.
- `hardware/motor_controller.py` – rotation math (use `MockStepperMotorController`).
- `database/db.py` – repository operations (`add_or_update_item`, `log_usage`).

Integration tests can:

1. Start the Flask app.
2. Call `/api/scan` with the camera disabled and verify graceful errors.
3. Insert mock clothing rows into SQLite, then call `/api/recommend` and
   `/api/confirm` and inspect DB changes.

## Assumptions & Constraints

- No RFID or other tags are used; **all detection is camera-only**.
- Carousel holds at least **40 slots**, evenly spaced.
- At boot, slot 0 is assumed to be aligned with the pickup point.
- For safety, the real system should be extended with:
  - A homing sensor / limit switch for absolute positioning.
  - Motor stall detection and emergency stop.
  - Enclosure interlock switches.

## Future Expansion Notes

- **Multiple users**: Add a `users` table and per-user preferences +
  usage history to personalize recommendations.
- **Cloud sync**: Sync the SQLite DB or higher-level events to a cloud
  backend using REST or MQTT, enabling cross-device history.
- **Better ML models**: Replace the heuristic classifier with a compact
  CNN (e.g., TensorFlow Lite) trained on garment images, while keeping
  the same `ClothingDetector` API.
- **Voice control**: Integrate a lightweight speech recognizer on the
  Raspberry Pi to trigger commands like "pick a formal outfit".
- **Mobile app integration**: Expose the same backend as a REST API for
  a companion mobile app that can pre-select outfits remotely.

