import os
import secrets
from pathlib import Path
from flask import Flask
from dotenv import load_dotenv
from .db import init_db, register_cli
from .routes import bp


def create_app(config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY'),
        DATABASE=os.getenv('DATABASE', 'instance/demobank.sqlite'),
        BANK_ORIGIN=os.getenv('BANK_ORIGIN', 'http://bank.localhost:5000').rstrip('/'),
        TRUSTED_HOSTS=os.getenv('BANK_HOSTS', 'bank.localhost,localhost,127.0.0.1').split(','),
        DEFAULT_CSRF_MODE=os.getenv('DEFAULT_CSRF_MODE', 'vulnerable'),
        PLAYGROUND_URL=os.getenv('PLAYGROUND_URL', 'http://evil.bank.localhost:5001/playground'),
        SESSION_COOKIE_NAME='demobank_session', SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.getenv('COOKIE_SAMESITE', 'Lax'),
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
        LAB_ACCESS_CODE=os.getenv('LAB_ACCESS_CODE', ''), MAX_CONTENT_LENGTH=16384,
    )
    if config:
        app.config.update(config)
    if not app.config['SECRET_KEY'] or len(app.config['SECRET_KEY']) < 32:
        raise RuntimeError('Set SECRET_KEY to at least 32 random characters in .env')
    if app.config['SESSION_COOKIE_SAMESITE'] not in ('Lax', 'Strict', 'None'):
        raise RuntimeError('COOKIE_SAMESITE must be Lax, Strict or None')
    if app.config['SESSION_COOKIE_SAMESITE'] == 'None' and not app.config['SESSION_COOKIE_SECURE']:
        raise RuntimeError('SameSite=None requires COOKIE_SECURE=true and browser HTTPS')
    if app.config['DEFAULT_CSRF_MODE'] not in ('protected', 'vulnerable'):
        raise RuntimeError('Invalid DEFAULT_CSRF_MODE')
    Path(app.config['DATABASE']).resolve().parent.mkdir(parents=True, exist_ok=True)
    app.register_blueprint(bp)
    from .admin import bp as admin_bp, is_admin
    app.register_blueprint(admin_bp)
    register_cli(app)
    with app.app_context():
        init_db()
    from .endpoints import endpoints, check_host, LabSessionInterface
    app.config['BASE_TRUSTED_HOSTS'] = app.config['TRUSTED_HOSTS'] or []
    app.config['TRUSTED_HOSTS'] = None
    app.before_request_funcs.setdefault(None, []).insert(0, check_host)
    app.session_interface = LabSessionInterface()
    @app.context_processor
    def helpers():
        from .security import token, settings
        return dict(csrf_token=token, lab=settings(), endpoints=endpoints(), is_admin=is_admin(), money=lambda n: f'NT${n / 100:,.2f}')
    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        response.headers['Referrer-Policy'] = 'same-origin'
        return response
    return app
