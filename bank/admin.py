import sqlite3
from functools import wraps
from flask import Blueprint, session, abort, render_template, request, redirect, url_for, flash, current_app
from .db import connect, reset_system
from .routes import login_required
from .security import verify_token
from .demo import HACKER_USERNAME

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/password',methods=['GET','POST'])
def password_page():
    return password_impl()


def is_admin():
    if not session.get('uid'):
        return False
    with connect() as db:
        row = db.execute("SELECT is_admin FROM users WHERE id=? AND EXISTS (SELECT 1 FROM metadata WHERE key='generation' AND value=?)", (session['uid'], session.get('generation'))).fetchone()
    return bool(row and row['is_admin'])

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if not is_admin():
            abort(403, '此頁面僅限管理員')
        return fn(*args, **kwargs)
    return wrapped

@admin_required
def password_impl():
    from werkzeug.security import check_password_hash
    if session.get('uid'):
        with connect() as db:
            user=db.execute('SELECT username,password_hash FROM users WHERE id=?',(session['uid'],)).fetchone()
    if user['username']!='pony':abort(403,'此功能限 pony 教師帳戶')
    if request.method=='POST':
        verify_token()
        if not check_password_hash(user['password_hash'],request.form.get('old_password','')):abort(403,'目前密碼不正確')
        password=request.form.get('new_password','')
        if not 8<=len(password)<=128 or password!=request.form.get('confirmation'):abort(400,'新密碼需 8–128 字元且確認一致')
        from teacher_password import sync_password
        from attacks.lab import database
        try: generation,_=sync_password(current_app.config['DATABASE'],database(),password)
        except ValueError as error:abort(400,str(error))
        session['generation']=generation
        session.pop('csrf',None)
        flash('各 Lab 的 pony 密碼與 JSON 紀錄已同步，其他登入已失效。')
        return redirect(url_for('admin.dashboard'))
    return render_template('teacher_password.html')

@bp.post('/endpoints')
@admin_required
def save_endpoints():
    import json
    from .endpoints import normalize_origin
    verify_token()
    try:
        bank = normalize_origin(request.form.get('bank',''))
        playground = normalize_origin(request.form.get('playground',''))
        if bank == playground:
            raise ValueError('銀行與活動網站必須使用不同 Origin')
        cross_site = request.form.get('cross_site') == 'on'
        if cross_site and (not bank.startswith('https://') or not playground.startswith('https://')):
            raise ValueError('跨 Site Cookie 模式需兩站皆為 HTTPS')
    except ValueError as err:
        abort(400, str(err))
    with connect() as db:
        db.execute("INSERT INTO metadata(key,value) VALUES ('public_endpoints',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps({'bank':bank,'playground':playground+'/playground','cross_site':cross_site}),))
    flash('端點已儲存並立即套用。學生請使用新網址重新登入，活動頁請重新整理。')
    return redirect(url_for('admin.dashboard'))

@bp.get('/')
@admin_required
def dashboard():
    with connect() as db:
        rows = db.execute('SELECT u.username,u.is_admin,a.number,a.balance FROM users u JOIN accounts a ON a.user_id=u.id ORDER BY u.is_admin DESC,u.id').fetchall()
    students = sum(not r['is_admin'] and r['username'] != HACKER_USERNAME for r in rows)
    hacker = next(r for r in rows if r['username'] == HACKER_USERNAME)
    return render_template('admin.html', rows=rows, students=students, hacker=hacker, hacker_name=HACKER_USERNAME)

@bp.post('/reset')
@admin_required
def reset():
    verify_token()  # Never follows the vulnerable transfer setting.
    if request.form.get('confirmation') != 'RESET':
        abort(400, '請輸入 RESET 確認重置')
    try:
        with connect() as db:
            generation = reset_system(db)
    except sqlite3.DatabaseError:
        current_app.logger.exception('Admin reset failed')
        abort(503, '重置未完成，請稍後再試')
    session['generation'] = generation
    session.pop('csrf', None)
    flash('系統已重置：學生帳號與交易已清除，管理員及駭客帳戶保留，餘額各恢復 NT$5,000。')
    return redirect(url_for('admin.dashboard'))
