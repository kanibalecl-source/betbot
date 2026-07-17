#!/usr/bin/env sh
set -eu

# One production entry point. It performs the persistent-volume guard before
# starting the scheduler, settlement worker and dashboard.
exec python -u app_launcher.py
