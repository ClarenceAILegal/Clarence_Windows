#!/usr/bin/env bash
# Render build command (also works locally)
set -euo pipefail
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -c "from motion_bot.web.app import app; print('build ok:', app.title)"
