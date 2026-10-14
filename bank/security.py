import secrets
from flask import session, request, abort, current_app

def token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']

def verify_token():
    supplied = request.form.get('csrf_token', '')
    expected = session.get('csrf', '')
    if not expected or not secrets.compare_digest(supplied, expected):
        abort(403, 'CSRF Token 缺少或不正確')

def settings():
    # Future labs are independent registry entries; unimplemented labs remain disabled.
    return {'csrf': session.get('csrf_mode', current_app.config['DEFAULT_CSRF_MODE']),
            'origin': session.get('origin_check', False),
            'xss': False, 'cors': False, 'sqli': False, 'idor': False}

def verify_transfer():
    if settings()['csrf'] == 'protected':
        verify_token()
    from .endpoints import endpoints
    if settings()['origin'] and request.headers.get('Origin') != endpoints()['bank']:
        abort(403, 'Origin 不在允許清單（缺少 Origin 也拒絕）')
