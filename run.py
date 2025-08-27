import asyncio
from watchfiles import run_process
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig
from src.server import app
from src.config import Config
from src.utils.server_utils import print_debug_banner

def start_dev_server():
    
    async def dev_main():
        hyper_conf = HyperConfig()
        hyper_conf.bind = [f"{Config.HOST}:{Config.PORT}"]
        hyper_conf.use_reloader = False
        hyper_conf.accesslog = "-"
        hyper_conf.errorlog = "-"
        hyper_conf.worker_class = "asyncio"
        hyper_conf.workers = 1
        
        print_debug_banner()
        print(f"Starting development server on {Config.HOST}:{Config.PORT}")
        print("Watching for file changes...")
        
        await serve(app, hyper_conf)
    
    asyncio.run(dev_main())

if __name__ == "__main__":
    run_process(".", target=start_dev_server, watch_filter=lambda change, path: 
                path.endswith(('.py', '.json', '.env')) and 
                not path.endswith('.pyc') and 
                '__pycache__' not in path)