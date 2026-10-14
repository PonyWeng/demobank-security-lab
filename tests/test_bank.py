import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from bank import create_app

@pytest.fixture
def app(tmp_path):
    return create_app({'TESTING': True, 'DEFAULT_CSRF_MODE': 'protected', 'SECRET_KEY': 'test-secret-' * 4, 'DATABASE': str(tmp_path / 'bank.sqlite'), 'TRUSTED_HOSTS': ['localhost'], 'LAB_ACCESS_CODE': '', 'SESSION_COOKIE_SECURE': False, 'SESSION_COOKIE_SAMESITE': 'Lax'})

def token(client, page='/bank'):
    response = client.get(page,follow_redirects=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text)[1]

def register(client, name):
    return client.post('/register', data={'csrf_token': token(client, '/register'), 'username': name, 'password': 'test-pass-123'})

def login(client, name):
    return client.post('/login', data={'csrf_token': token(client, '/login'), 'username': name, 'password': 'test-pass-123'})

def setup_accounts(app):
    a, b = app.test_client(), app.test_client()
    assert register(a, 'alice').status_code == 302
    assert register(b, 'bob').status_code == 302
    assert login(a, 'alice').status_code == 302
    assert login(b, 'bob').status_code == 302
    return a, b

def mode(client, value, origin=False):
    return client.post('/lab', data={'csrf_token': token(client, '/lab'), 'mode': value, **({'origin': 'on'} if origin else {})})

def test_acceptance(app):
    a, b = setup_accounts(app)
    aa, bb = a.get('/api/account').json['account'], b.get('/api/account').json['account']
    assert aa['balance'] == bb['balance'] == 500000
    assert aa['number'] != bb['number']
    assert a.post('/transfer', data={'csrf_token': token(a), 'recipient': bb['number'], 'amount': '123.45', 'sender': bb['id']}).status_code == 302
    assert a.get('/api/account').json['account']['balance'] == 487655
    assert b.get('/api/account').json['account']['balance'] == 512345
    assert len(a.get('/api/account').json['transactions']) == len(b.get('/api/account').json['transactions']) == 1
    mode(a, 'vulnerable')
    forged = {'recipient': bb['number'], 'amount': '100'}
    assert a.post('/transfer', data=forged, headers={'Origin': 'http://evil.localhost:5001'}).status_code == 302
    mode(a, 'protected')
    assert a.post('/transfer', data=forged, headers={'Origin': 'http://evil.localhost:5001'}).status_code == 403
    mode(a, 'vulnerable', True)
    assert a.post('/transfer', data=forged, headers={'Origin': 'http://evil.localhost:5001'}).status_code == 403
    assert a.post('/transfer', data=forged).status_code == 403
    assert a.post('/transfer', data=forged, headers={'Origin': app.config['BANK_ORIGIN']}).status_code == 302
    assert b.get('/lab').text.count('Protected · 驗證 Token') == 1
    assert a.post('/logout', data={'csrf_token': token(a)}).status_code == 302
    assert a.get('/api/account').status_code == 302
    assert login(a, 'alice').status_code == 302
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT sum(balance) FROM accounts').fetchone()[0] == 1500000
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert 'test-pass' not in db.execute('SELECT password_hash FROM users LIMIT 1').fetchone()[0]

@pytest.mark.parametrize('amount', ['0', '-1', 'NaN', 'Infinity', '1.001', '100000000000000', 'nope', '5000.01'])
def test_invalid_amount_rollback(app, amount):
    a, b = setup_accounts(app)
    recipient = b.get('/api/account').json['account']['number']
    assert a.post('/transfer', data={'csrf_token': token(a), 'recipient': recipient, 'amount': amount}).status_code == 400
    assert a.get('/api/account').json['account']['balance'] == 500000
    assert not b.get('/api/account').json['transactions']

def test_auth_and_ownership(app):
    a, b = setup_accounts(app)
    account = a.get('/api/account').json['account']
    for recipient in [account['number'], "' OR 1=1 --", 'missing']:
        assert a.post('/transfer', data={'csrf_token': token(a), 'recipient': recipient, 'amount': '1'}).status_code == 400
    assert a.get('/api/account?user_id=2').json['account']['username'] == 'alice'
    assert a.post('/lab', data={'mode': 'vulnerable'}).status_code == 403
    assert a.post('/logout').status_code == 403
    assert a.get('/logout').status_code == 405
    assert a.post('/transfer', data={'csrf_token': token(b), 'amount': '1'}).status_code == 403
    assert a.post('/register', data={'csrf_token': token(a, '/register'), 'username': 'alice', 'password': 'test-pass-123'}).status_code == 200
    assert '帳號已存在' in a.get('/register').text or a.get('/api/account').json['account']['balance'] == 500000
    app.test_cli_runner().invoke(args=['reset-lab', '--yes'])
    # Register new user reusing SQLite id: old session must still fail.
    fresh = app.test_client()
    register(fresh, 'carol')
    assert a.get('/api/account').status_code == 302

def test_concurrent_transfer(app):
    a, b = setup_accounts(app)
    token(a)
    with a.session_transaction() as s:
        state = dict(s)
    recipient = b.get('/api/account').json['account']['number']
    def send(_):
        client = app.test_client()
        with client.session_transaction() as s:
            s.update(state)
        return client.post('/transfer', data={'csrf_token': state['csrf'], 'recipient': recipient, 'amount': '3000'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(send, range(2))) == [302, 400]
    assert a.get('/api/account').json['account']['balance'] == 200000
    assert b.get('/api/account').json['account']['balance'] == 800000

def test_cookie_configuration_and_gate(tmp_path):
    with pytest.raises(RuntimeError):
        create_app({'SECRET_KEY': 's' * 32, 'SESSION_COOKIE_SAMESITE': 'None', 'SESSION_COOKIE_SECURE': False})
    app = create_app({'SECRET_KEY': 's' * 32, 'DATABASE': str(tmp_path / 'gate.db'), 'LAB_ACCESS_CODE': 'course', 'TRUSTED_HOSTS': ['localhost']})
    client = app.test_client()
    assert client.get('/register').location.endswith('/access')
    assert client.post('/access', data={'csrf_token': token(client, '/access'), 'code': 'course'}).status_code == 302
    assert client.get('/register').status_code == 200

def test_database_failure_rolls_back(app):
    a, b = setup_accounts(app)
    recipient = b.get('/api/account').json['account']['number']
    with sqlite3.connect(app.config['DATABASE']) as db:
        db.execute("CREATE TRIGGER simulate_failure BEFORE INSERT ON transfers BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    assert a.post('/transfer', data={'csrf_token': token(a), 'recipient': recipient, 'amount': '100'}).status_code == 503
    assert a.get('/api/account').json['account']['balance'] == 500000
    assert b.get('/api/account').json['account']['balance'] == 500000
    assert not a.get('/api/account').json['transactions']
