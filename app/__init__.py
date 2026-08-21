from flask import Flask
from config import Config
from app.models import db, User
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        import sys, importlib
        if 'app.routes' in sys.modules:
            importlib.reload(sys.modules['app.routes'])
        else:
            from app import routes

        from app.ai_routes import ai_bp, ai_ui_bp
        if 'ai' not in app.blueprints:
            app.register_blueprint(ai_bp)
        if 'ai_ui' not in app.blueprints:
            app.register_blueprint(ai_ui_bp)

        # Automatically create tables if they do not exist
        db.create_all()

        # In production and normal runs, automatically seed system vocabulary on startup
        if not app.config.get('TESTING', False):
            from seed import auto_init_and_seed
            auto_init_and_seed(app)

    return app
