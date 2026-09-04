python -m src.daily_pick --help >/dev/null 2>&1 && echo "cli ok"
python scripts/status.py 2>&1 | tail -12
