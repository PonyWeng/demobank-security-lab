import re
import secrets
import sqlite3
from decimal import Decimal, InvalidOperation
from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, abort, current_app, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from .db import connect
from .security import verify_token, verify_transfer
from .demo import HACKER_USERNAME

bp = Blueprint('bank', __name__)

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with connect() as db:
            generation = db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()['value']
            user = db.execute('SELECT id FROM users WHERE id=?', (session.get('uid'),)).fetchone()
            portal_valid=not session.get('portal_session') or db.execute('SELECT 1 FROM portal_sessions WHERE id=? AND user_id=?',(session.get('portal_session'),session.get('uid'))).fetchone()
        if not user or not portal_valid or session.get('generation') != generation:
            if session.get('uid') is not None:
                session.clear()
            if request.endpoint == 'bank.transfer':
                if request.args.get('reward') == '1':
                    return render_template('reward_notice.html'), 401
                abort(401, '沒有登入 Cookie；請先登入或檢查 SameSite 設定')
            return redirect(url_for('bank.login'))
        return fn(*args, **kwargs)
    return wrapped

@bp.before_request
def gate():
    code = current_app.config['LAB_ACCESS_CODE']
    if code and not session.get('gate') and request.endpoint not in ('bank.access', 'static'):
        return redirect(url_for('bank.access', **({'reward': '1'} if request.args.get('reward') == '1' else {})))

@bp.route('/access', methods=['GET', 'POST'])
def access():
    if request.method == 'POST':
        verify_token()
        if secrets.compare_digest(request.form.get('code', ''), current_app.config['LAB_ACCESS_CODE']):
            session['gate'] = True
            return redirect(url_for('bank.login', **({'reward': '1'} if request.args.get('reward') == '1' else {})))
        flash('課程代碼不正確')
    return render_template('auth.html', kind='access')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        verify_token()
        name, password = request.form.get('username', '').strip(), request.form.get('password', '')
        if name.casefold() == HACKER_USERNAME.casefold():
            flash('此帳號保留給模擬駭客，請使用其他名稱')
        elif not re.fullmatch(r'[A-Za-z0-9_]{3,32}', name) or not 8 <= len(password) <= 128:
            flash('帳號需為 3–32 字元英數或底線；密碼需 8–128 字元')
        else:
            try:
                with connect() as db:
                    uid = db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)', (name, generate_password_hash(password))).lastrowid
                    db.execute('INSERT INTO accounts(user_id,number,balance) VALUES (?,?,500000)', (uid, 'DB' + secrets.token_hex(6).upper()))
                gate_ok=session.get('gate',False)
                session.clear()
                from portal_auth import create_login
                with connect() as db:
                    generation=db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()['value']
                    identifier=create_login(db,uid)
                session.update(uid=uid,generation=generation,gate=gate_ok,portal_session=identifier)
                flash('註冊完成，已存入 NT$5,000；請選擇 Lab。')
                return redirect(url_for('bank.lab_hub'))
            except sqlite3.IntegrityError:
                flash('帳號已存在，請使用其他名稱')
    return render_template('auth.html', kind='register')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method=='GET' and session.get('uid'):
        with connect() as db:
            user=db.execute('SELECT id FROM users WHERE id=?',(session['uid'],)).fetchone()
            generation=db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()['value']
            portal_valid=not session.get('portal_session') or db.execute('SELECT 1 FROM portal_sessions WHERE id=? AND user_id=?',(session['portal_session'],session['uid'])).fetchone()
        if user and portal_valid and session.get('generation')==generation:
            return redirect(url_for('bank.reward_return' if request.args.get('reward')=='1' else 'bank.lab_hub'))
        gate_ok=session.get('gate',False)
        session.clear();session['gate']=gate_ok
    if request.method == 'POST':
        verify_token()
        with connect() as db:
            user = db.execute('SELECT * FROM users WHERE username=?', (request.form.get('username', ''),)).fetchone()
            generation = db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()['value']
        if user and check_password_hash(user['password_hash'], request.form.get('password', '')):
            gate_ok = session.get('gate', False)
            session.clear()
            session.update(uid=user['id'], generation=generation, gate=gate_ok)
            from portal_auth import create_login
            with connect() as db:session['portal_session']=create_login(db,user['id'])
            if request.args.get('reward') == '1':
                return redirect(url_for('bank.reward_return'))
            return redirect(url_for('bank.lab_hub'))
        flash('帳號或密碼不正確')
    if request.method == 'GET' and request.args.get('reward') == '1':
        flash('尚未登入或此次請求未帶登入 Cookie。請先登入 DemoBank，再回活動頁按一次「領取活動獎勵」。')
    return render_template('auth.html', kind='login')

@bp.post('/logout')
@login_required
def logout():
    verify_token()
    with connect() as db:db.execute('DELETE FROM portal_sessions WHERE id=?',(session.get('portal_session'),))
    session.clear()
    return redirect(url_for('bank.login'))

@bp.get('/reward-return')
@login_required
def reward_return():
    if request.args.get('outcome') == 'success':
        from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
        from .endpoints import endpoints
        parts = urlsplit(endpoints()['playground'])
        query = dict(parse_qsl(parts.query))
        query['reward_result'] = 'success'
        destination = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        return render_template('reward_return.html', destination=destination)
    return render_template('reward_return.html')

def account_data():
    with connect() as db:
        account = db.execute('SELECT a.*, u.username FROM accounts a JOIN users u ON a.user_id=u.id WHERE a.user_id=?', (session['uid'],)).fetchone()
        history = db.execute('SELECT t.*, s.number AS sender_number, r.number AS recipient_number FROM transfers t JOIN accounts s ON s.id=t.sender JOIN accounts r ON r.id=t.recipient WHERE t.sender=? OR t.recipient=? ORDER BY t.id DESC LIMIT 100', (account['id'], account['id'])).fetchall()
    return account, history

@bp.get('/bank')
@login_required
def dashboard():
    account, history = account_data()
    return render_template('dashboard.html', account=account, history=history)

@bp.get('/api/account')
@login_required
def api_account():
    account, history = account_data()
    return jsonify(account=dict(account), transactions=[dict(t) for t in history])

@bp.get('/labs')
@login_required
def lab_hub():
    from .endpoints import endpoints
    from attacks.lab import urls,initialize
    initialize()
    return render_template('lab_hub.html',bank_urls=endpoints(),attack_urls=urls())

@bp.get('/')
def home():
    return redirect(url_for('bank.lab_hub'))

@bp.get('/labs/enter/<kind>')
@login_required
def enter_lab(kind):
    from portal_auth import issue
    from attacks.lab import urls,initialize
    if kind not in ('sql','xss','collector'):abort(404)
    initialize()
    ticket,identifier=issue(current_app.config['DATABASE'],session['uid'],kind,session.get('portal_session'))
    session['portal_session']=identifier
    return redirect(urls()[kind]+'/auth/entry?ticket='+ticket)

@bp.post('/transfer')
@login_required
def transfer():
    verify_transfer()
    try:
        value = Decimal(request.form.get('amount', ''))
        if not value.is_finite() or value <= 0 or value > Decimal('10000000') or value != value.quantize(Decimal('.01')):
            raise ValueError()
        amount = int(value * 100)
    except (InvalidOperation, ValueError):
        abort(400, '金額需為正數，最多兩位小數')
    try:
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            sender = db.execute('SELECT * FROM accounts WHERE user_id=?', (session['uid'],)).fetchone()
            recipient = db.execute('SELECT * FROM accounts WHERE number=?', (request.form.get('recipient', '').strip(),)).fetchone()
            if not recipient or recipient['id'] == sender['id']:
                abort(400, '收款帳戶不存在或為自己的帳戶')
            if sender['balance'] < amount:
                abort(400, '餘額不足')
            db.execute('UPDATE accounts SET balance=balance-? WHERE id=?', (amount, sender['id']))
            db.execute('UPDATE accounts SET balance=balance+? WHERE id=?', (amount, recipient['id']))
            db.execute('INSERT INTO transfers(sender,recipient,amount) VALUES (?,?,?)', (sender['id'], recipient['id'], amount))
    except sqlite3.DatabaseError:
        current_app.logger.exception('Transfer database operation failed')
        abort(503, '資料庫暫時無法完成交易，請稍後再試')
    if request.args.get('reward') == '1':
        return redirect(url_for('bank.reward_return', outcome='success'), code=303)
    flash('轉帳完成')
    return redirect(url_for('bank.dashboard'))

@bp.route('/lab', methods=['GET', 'POST'])
@login_required
def lab():
    if request.method == 'POST':
        verify_token()  # Always protected, even when transfer lab is vulnerable.
        mode = request.form.get('mode')
        if mode not in ('protected', 'vulnerable'):
            abort(400)
        from .security import settings
        before = settings()
        origin = request.form.get('origin') == 'on'
        changes = []
        if before['csrf'] != mode:
            changes.append('CSRF Token：' + ('由停用改為啟用，轉帳前驗證 Token。' if mode == 'protected' else '由啟用改為停用，轉帳略過 Token 驗證。'))
        if before['origin'] != origin:
            changes.append('Origin 驗證：' + ('由停用改為啟用，轉帳前比對銀行來源。' if origin else '由啟用改為停用，不比對請求來源。'))
        session['lab_changes'] = changes or ['設定未變更；目前防護維持原狀。']
        session['csrf_mode'] = mode
        session['origin_check'] = request.form.get('origin') == 'on'
        flash('實驗設定已更新，只影響你的 Session')
        return redirect(url_for('bank.lab'))
    return render_template('lab.html', cookie=current_app.session_interface.get_cookie_samesite(current_app), secure=current_app.session_interface.get_cookie_secure(current_app))

@bp.app_errorhandler(400)
@bp.app_errorhandler(401)
@bp.app_errorhandler(403)
@bp.app_errorhandler(503)
def error(err):
    return render_template('error.html', error=err), err.code
