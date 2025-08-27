run prod:
hypercorn src.server:create_app --bind 0.0.0.0:5000 --workers 4 --log-level info

run dev:
python run.py
