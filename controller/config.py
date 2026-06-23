from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Renderer loop tuning (shared dev/prod; same env-var names as match-day-live).
FRAME_INTERVAL = float(os.environ.get("LED_FRAME_INTERVAL", "0.2"))
TRANSITION_SECONDS = float(os.environ.get("LED_TRANSITION", "0.5"))

# Web app port. 5050 is taken by match-day-live; avoid 5060/5061 — browsers
# block them as "unsafe" SIP ports (ERR_UNSAFE_PORT), so the preview won't load.
PORT = int(os.environ.get("PORT", "5070"))

# View shown on first run / when stored active key is unknown.
DEFAULT_ACTIVE = os.environ.get("PI_LED_DEFAULT_ACTIVE", "messages:main")
