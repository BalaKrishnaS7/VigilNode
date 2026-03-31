from flask import Flask
from flask_socketio import SocketIO
from config import Config
from app.database import init_db

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Init database
    init_db()

    # Register routes
    from app.routes import main
    app.register_blueprint(main)

    # Init SocketIO
    socketio.init_app(app)

    return app
