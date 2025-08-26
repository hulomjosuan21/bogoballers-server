import sys
from watchfiles import run_process

def start_server(init_scheduler: bool):
    import asyncio
    from src.server import main
    asyncio.run(main(init_scheduler_flag=init_scheduler))

if __name__ == "__main__":
    init_sched = "--worker" in sys.argv
    run_process(".", target=start_server, args=(init_sched,))