# Launch Smoke Check
Goal: catch a demo that imports cleanly in tests but dies on UI startup.
Run all tests with `pytest`.
Run only the smoke check with `pytest tests/test_launch_smoke.py`.
The smoke check runs `python -m karaoke_buddy --smoke-check`.
It forces Qt offscreen so CI and headless shells can run it.
It imports the UI modules and creates the main window.
It starts the Qt event loop briefly, then exits.
Failures print captured stdout and stderr.
No screenshot is needed because this is a startup check, not a visual change.
