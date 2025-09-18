from quart import Quart, jsonify
from quart_cors import cors
import socketio
from src.blueprints import all_blueprints
from src.config import Config
from src.extensions import sio, settings, redis_client, jwt
from quart_auth import QuartAuth
from src.utils.server_utils import check_db_connection, print_debug_banner, print_routes
import os
import asyncio

def create_app():
    app = Quart(__name__)
    app.config.from_object(Config)
    QuartAuth(app)

    if not app.secret_key:
        raise RuntimeError("SECRET_KEY must be set in Config")
    
    app.debug = Config.DEBUG
    app = cors(
        app,
        allow_origin=Config.CORS_ORIGINS,
        allow_credentials=True
    )

    @app.route("/ping")
    async def ping():
        return jsonify({"status": "ok", "message": "pong"}), 200

    for bp in all_blueprints:
        app.register_blueprint(bp)
        
    @app.before_serving
    async def startup():
        await check_db_connection()
        
        if settings.get("enable_worker", False):
            await start_worker_if_leader()

    @app.after_serving
    async def shutdown():
        await cleanup_worker_lock()

    asgi_app = socketio.ASGIApp(sio, app)
    if Config.DEBUG:
        print_routes(app)
    return asgi_app

async def start_worker_if_leader():
    try:
        lock_acquired = await redis_client.set(
            "worker_leader_lock", 
            os.getpid(), 
            nx=True,
            ex=30
        )
        
        if lock_acquired:
            print(f"Process {os.getpid()} acquired worker leadership")
            
            from src.worker import Worker
            from src.task import Task
            
            task_instance = Task()
            worker = Worker(task_instance)
            worker.start()
            
            asyncio.create_task(maintain_worker_leadership())
        else:
            current_leader = await redis_client.get("worker_leader_lock")
            print(f"Worker already running in process {current_leader}, this process ({os.getpid()}) will skip worker startup")
            
    except Exception as e:
        print(f"Error starting worker: {e}")

async def maintain_worker_leadership():
    while True:
        try:
            await asyncio.sleep(20)
            await redis_client.expire("worker_leader_lock", 30)
        except Exception as e:
            print(f"Error maintaining worker leadership: {e}")
            break

async def cleanup_worker_lock():
    try:
        current_leader = await redis_client.get("worker_leader_lock")
        if current_leader == str(os.getpid()):
            await redis_client.delete("worker_leader_lock")
            print(f"Process {os.getpid()} released worker leadership")
    except Exception as e:
        print(f"Error cleaning up worker lock: {e}")

app = create_app()