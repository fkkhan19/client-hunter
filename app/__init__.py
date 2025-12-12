from flask import Flask
from .config import Config
from .db import db
from .dashboard.routes import dashboard

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Init DB
    db.init_app(app)

    # Register dashboard blueprint
    app.register_blueprint(dashboard)

    # Create DB tables
    with app.app_context():
        db.create_all()

    # ❌ DO NOT START THE SCHEDULER HERE

    return app
