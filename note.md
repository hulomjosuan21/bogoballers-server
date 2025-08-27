prod:
hypercorn src.server:app --bind 0.0.0.0:5000 --workers 4 --log-level info

dev:
python run.py

test_local:
hypercorn src.server:app --bind 127.0.0.1:5000 --workers 1 --log-level debug --reload
