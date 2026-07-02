#!/bin/bash
# Quick start for StudyTrack on Mac/Linux.
set -e
cd "$(dirname "$0")"
pip install -r requirements.txt
python3 app.py
