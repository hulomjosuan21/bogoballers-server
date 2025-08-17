import os
import sys
import subprocess

BASE_DIR = os.path.dirname(__file__)
ALEMBIC_DIR = os.path.join(BASE_DIR, "migrations")

def alembic_cmd(*args):
    subprocess.run(["alembic", *args])

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "makemigration":
        alembic_cmd("revision", "--autogenerate", "-m", sys.argv[2] if len(sys.argv) > 2 else "update")
    elif cmd == "migrate":
        alembic_cmd("upgrade", "head")
    else:
        print("Usage: python cli.py [makemigration 'msg' | migrate]")
