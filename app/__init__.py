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
        app.register_blueprint(ai_bp)
        app.register_blueprint(ai_ui_bp)
        return app
