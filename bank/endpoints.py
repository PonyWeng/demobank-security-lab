import json
from urllib.parse import urlsplit
from flask import current_app, request, abort
from flask.sessions import SecureCookieSessionInterface
from .db import connect

def normalize_origin(value):
    value = value.strip().rstrip('/')
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise ValueError('網址格式或連接埠不正確')
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password or parts.path or parts.query or parts.fragment or any(c.isspace() for c in value):
        raise ValueError('請輸入 http(s)://主機[:port]，不含路徑、帳密或參數')
    if not all(c.isalnum() or c in '.-:' for c in parts.hostname):
        raise ValueError('主機名稱不正確')
    return value

def endpoints():
    with connect() as db:
        row = db.execute("SELECT value FROM metadata WHERE key='public_endpoints'").fetchone()
    if row:
        return json.loads(row['value'])
    return {'bank':current_app.config['BANK_ORIGIN'], 'playground':current_app.config['PLAYGROUND_URL'], 'cross_site':False}

def check_host():
    saved = endpoints()
    allowed = set(current_app.config['BASE_TRUSTED_HOSTS'])
    allowed.add(urlsplit(saved['bank']).hostname)
    if request.host.split(':')[0] not in allowed:
        abort(400, '此銀行主機尚未由管理員設定')

class LabSessionInterface(SecureCookieSessionInterface):
    def get_cookie_samesite(self, app):
        if endpoints()['cross_site'] and request.host.split(':')[0] not in ('localhost','127.0.0.1','bank.localhost'):
            return 'None'
        return super().get_cookie_samesite(app)
    def get_cookie_secure(self, app):
        if endpoints()['cross_site'] and request.host.split(':')[0] not in ('localhost','127.0.0.1','bank.localhost'):
            return True
        return super().get_cookie_secure(app)
