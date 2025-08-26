import sys
from watchfiles import run_process

def start_server():
    import asyncio
    from src.server import main
    asyncio.run(main())

if __name__ == "__main__":
    run_process(".", target=start_server)