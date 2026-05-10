"""Pytest fixtures.

Force in-memory store and disable startup seeding regardless of .env values.
Tests run fast and never hit Google Sheets.
"""

import os

# Disable Sheets/Gemini and skip seeding for the entire test session.
# These must be set BEFORE any app modules are imported.
os.environ["GOOGLE_SHEETS_ID"] = ""
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["GEMINI_API_KEY"] = ""
