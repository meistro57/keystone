#!/usr/bin/env bash
# filename: setup.sh
set -e
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
echo "Keystone ready. Edit .env, then:  python run.py --dry-run"
