import asyncio
from watchfiles import run_process
from src.server import main

def start_server():
    asyncio.run(main())

if __name__ == "__main__":
    run_process(".", target=start_server)
