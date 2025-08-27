from quart import Quart, jsonify
from quart_cors import cors
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig
import socketio
from src.blueprints import all_blueprints
from src.config import Config
from src.extensions import sio, settings
from quart_auth import QuartAuth
from src.utils.server_utils import check_db_connection, print_debug_banner, print_routes

def create_app():
    app = Quart(__name__)
    app.config.from_object(Config)
    QuartAuth(app)

    if not app.secret_key:
        raise RuntimeError("SECRET_KEY must be set in Config")

    app.debug = True
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
            from src.worker import Worker
            from src.task import Task
            task_instance = Task()
            worker = Worker(task_instance)
            worker.start()

    asgi_app = socketio.ASGIApp(sio, app)
    print_routes(app)
    return asgi_app

app = create_app()

async def main():
    hyper_conf = HyperConfig()
    hyper_conf.bind = [f"{Config.HOST}:{Config.PORT}"]
    hyper_conf.use_reloader = True
    hyper_conf.accesslog = "-"
    hyper_conf.errorlog = "-"
    hyper_conf.worker_class = "asyncio"
    print_debug_banner()
    await serve(app, hyper_conf)
