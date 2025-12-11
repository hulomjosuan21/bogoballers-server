import logging
from quart import Quart, jsonify
from quart_cors import cors
import socketio
from src.container import cluster_worker, scheduler_manager
from src.blueprints import all_blueprints
from quart_jwt_extended import JWTManager
from src.config import Config
from src.extensions import sio
from quart_auth import QuartAuth
from src.utils.server_utils import check_db_connection, print_routes

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logging.getLogger("apscheduler").setLevel(logging.WARNING) 


def create_app():
    app = Quart(__name__)
    app.config.from_object(Config)
    QuartAuth(app)
    JWTManager(app)

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

    @app.route("/stop-cleanup")
    async def stop_cleanup():
        removed = scheduler_manager.remove_job("cleanup_service")
        return jsonify({"status": "removed" if removed else "not_found"}), 200

    for bp in all_blueprints:
        app.register_blueprint(bp)
        
    @app.before_serving
    async def startup():
        await check_db_connection()
        await cluster_worker.start()

    @app.after_serving
    async def shutdown():
        await cluster_worker.stop()

    asgi_app = socketio.ASGIApp(sio, app)
    if Config.DEBUG:
        print_routes(app)
    return asgi_app

app = create_app()