import os, sqlite3, secrets, json
from pathlib import Path
from functools import wraps
from urllib.parse import urlsplit
from flask import Flask, request, session, redirect, render_template, abort, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parent
def config_value(key, default=''):
    return os.getenv('ATTACKS_'+key, dotenv_values(ROOT/'.env').get(key, default))

def database():
    path=Path(config_value('DATABASE','instance/attacks.sqlite'))
    return path if path.is_absolute() else ROOT/path

def db():
    c=sqlite3.connect(database(),timeout=10)
    c.row_factory=sqlite3.Row
    return c

def initialize():
    database().parent.mkdir(parents=True,exist_ok=True)
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password_hash TEXT,is_admin INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,username TEXT,content TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS captures(id INTEGER PRIMARY KEY,content TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);''')
        c.execute("INSERT OR IGNORE INTO settings VALUES ('generation',?)",(secrets.token_hex(16),))

def urls():
    with db() as c:
        row=c.execute("SELECT value FROM settings WHERE key='urls'").fetchone()
    return json.loads(row['value']) if row else {'sql':'http://sql.localhost:5100','xss':'http://xss.localhost:5101','collector':'http://collector.localhost:5102'}

def create_app(kind,config=None):
    initialize()
    app=Flask(__name__)
    app.config.update(SECRET_KEY=config_value('SECRET_KEY'),SESSION_COOKIE_NAME=f'attacks_{kind}',SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE=config_value('COOKIE_SAMESITE','Lax'),SESSION_COOKIE_SECURE=config_value('COOKIE_SECURE','false')=='true')
    if config: app.config.update(config)
    if not app.secret_key or len(app.secret_key)<32: raise RuntimeError('Run setup first to create SECRET_KEY')
    def token():
        if 'token' not in session: session['token']=secrets.token_urlsafe(32)
        return session['token']
    def verify():
        if not session.get('token') or not secrets.compare_digest(session['token'],request.form.get('csrf_token','')): abort(403,'Invalid CSRF Token')
    def logged():
        with db() as c:
            generation=c.execute("SELECT value FROM settings WHERE key='generation'").fetchone()['value']
        return session.get('username') and session.get('generation')==generation
    def teacher():
        if not logged() or not session.get('teacher'): abort(403,'Teacher login required')
        with db() as c:
            u=c.execute('SELECT is_admin FROM users WHERE username=?',(session['username'],)).fetchone()
        if not u or not u['is_admin']: abort(403)
    @app.context_processor
    def helpers():
        return dict(kind=kind,token=token,urls=urls(),mode=session.get('mode','vulnerable'),teacher=bool(logged() and session.get('teacher')))
    @app.before_request
    def gate():
        host=request.host.split(':')[0]
        allowed={'localhost','127.0.0.1',f'{kind}.localhost',urlsplit(urls()[kind]).hostname}
        if host not in allowed: abort(400,'Host not configured; use localhost teacher admin first')
        if config_value('LAB_ACCESS_CODE') and not session.get('gate') and request.endpoint not in ('access','static'):
            if request.endpoint!='steal': return redirect('/access')
    @app.route('/access',methods=['GET','POST'])
    def access():
        if request.method=='POST':
            verify()
            if secrets.compare_digest(request.form.get('code',''),config_value('LAB_ACCESS_CODE','')):
                session['gate']=True
                return redirect('/')
            flash('課程代碼錯誤')
        return render_template('auth.html',access=True)
    @app.route('/register',methods=['GET','POST'])
    def register():
        if request.method=='POST':
            verify()
            name=request.form.get('username','').strip(); password=request.form.get('password','')
            if not name.isascii() or not name.replace('_','').isalnum() or not 3<=len(name)<=32 or not 8<=len(password)<=128: abort(400)
            try:
                with db() as c: c.execute('INSERT INTO users(username,password_hash) VALUES (?,?)',(name,generate_password_hash(password)))
                return redirect('/login')
            except sqlite3.IntegrityError: flash('帳號已存在')
        return render_template('xss_register.html' if kind=='xss' else 'auth.html',register=True)
    @app.route('/login',methods=['GET','POST'])
    @app.route('/teacher/login',methods=['GET','POST'])
    def login():
        is_teacher=request.path.startswith('/teacher')
        if request.method=='POST':
            verify()
            name=request.form.get('username',''); password=request.form.get('password','')
            with db() as c:
                real=c.execute('SELECT * FROM users WHERE username=?',(name,)).fetchone()
                valid=bool(real and check_password_hash(real['password_hash'],password))
                if kind=='sql' and not is_teacher and session.get('mode','vulnerable')=='vulnerable':
                    query=f"SELECT * FROM users WHERE username='{name}' AND 1={int(valid)}"
                    try: user=c.execute(query).fetchone()
                    except sqlite3.Error: user=None
                else: user=real if valid else None
                generation=c.execute("SELECT value FROM settings WHERE key='generation'").fetchone()['value']
            if user and (not is_teacher or user['is_admin']):
                mode=session.get('mode','vulnerable'); gate=session.get('gate',False)
                verified_admin=bool(valid and real and user['id']==real['id'] and user['is_admin'])
                session.clear();session.update(username=user['username'],teacher=verified_admin,generation=generation,mode=mode,gate=gate)
                return redirect('/admin' if is_teacher else '/')
            flash('登入失敗')
        return render_template(f'{kind}_login.html' if kind in ('sql','xss') else 'auth.html',is_teacher=is_teacher)
    @app.route('/',methods=['GET','POST'])
    def index():
        if kind=='collector':
            if not logged():return redirect('/login')
            with db() as c: rows=c.execute('SELECT * FROM captures ORDER BY id DESC LIMIT 100').fetchall()
            return render_template('collector.html',rows=rows)
        if not logged(): return redirect('/login')
        if kind=='sql' and request.method=='GET':
            with db() as c:
                tables=[]
                for name in ('users','messages','captures'):
                    columns=c.execute(f'PRAGMA table_info({name})').fetchall()
                    data=c.execute(f'SELECT * FROM {name} LIMIT 100').fetchall()
                    tables.append({'table':name,'columns':columns,'rows':data})
            return render_template('sql_index.html',db_info=tables,user=session['username'],isAdmin=int(session.get('teacher',False)))
        if request.method=='POST':
            verify()
            if kind=='xss':
                content=request.form.get('content','')
                if len(content)>10000: abort(400)
                with db() as c: c.execute('INSERT INTO messages(username,content) VALUES (?,?)',(session['username'],content))
            return redirect('/')
        with db() as c: rows=c.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 100').fetchall() if kind=='xss' else []
        return render_template('xss_board.html',messages=rows,user_id=session['username'])
    @app.post('/delete_message/<int:msg_id>')
    def delete_message(msg_id):
        if kind!='xss':abort(404)
        if not logged():abort(403)
        verify()
        with db() as c:
            row=c.execute('SELECT username FROM messages WHERE id=?',(msg_id,)).fetchone()
            if not row:abort(404)
            if row['username']!=session['username']:abort(403)
            c.execute('DELETE FROM messages WHERE id=?',(msg_id,))
        return redirect('/')
    @app.post('/admin/clear_messages')
    def clear_messages():
        teacher();verify()
        with db() as c:c.execute('DELETE FROM messages')
        return redirect('/')
    @app.route('/admin/users/add',methods=['GET','POST'])
    def add_user():
        teacher()
        message=''
        if request.method=='POST':
            verify()
            name=request.form.get('username','').strip();password=request.form.get('password','')
            if not name.isascii() or not name.replace('_','').isalnum() or not 3<=len(name)<=32 or not 8<=len(password)<=128:abort(400,'帳號或密碼格式不正確')
            try:
                with db() as c:c.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,?)',(name,generate_password_hash(password),int(request.form.get('isAdmin')=='on')))
                message='User added successfully!'
            except sqlite3.IntegrityError:message='User already exists.'
        return render_template('sql_add_user.html',message=message)
    @app.route('/security',methods=['GET','POST'])
    def security():
        if request.method=='POST':
            verify()
            if request.form.get('mode') not in ('vulnerable','protected'): abort(400)
            session['mode']=request.form['mode']
            flash('設定已套用，只影響本次 Session')
            return redirect('/security')
        return render_template('security.html')
    @app.route('/admin',methods=['GET','POST'])
    def admin():
        teacher()
        if request.method=='POST':
            verify()
            new={}
            for k in ('sql','xss','collector'):
                value=request.form.get(k,'').strip().rstrip('/');p=urlsplit(value)
                if p.scheme not in ('http','https') or not p.hostname or p.path or p.query or p.fragment or p.username or p.password or any(ch.isspace() for ch in value): abort(400)
                new[k]=value
            if len(set(new.values()))!=3: abort(400)
            with db() as c: c.execute("INSERT INTO settings VALUES ('urls',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(new),))
            return redirect('/admin')
        with db() as c: users=c.execute('SELECT username,is_admin FROM users').fetchall()
        return render_template('admin.html',users=users)
    @app.post('/admin/reset')
    def reset():
        teacher();verify()
        if request.form.get('confirmation')!='RESET':abort(400)
        with db() as c:
            c.execute('DELETE FROM messages');c.execute('DELETE FROM captures');c.execute('DELETE FROM users WHERE is_admin=0')
            generation=secrets.token_hex(16)
            c.execute("UPDATE settings SET value=? WHERE key='generation'",(generation,))
        session['generation']=generation
        flash('學生、留言與收集紀錄已清除，管理員及端點保留')
        return redirect('/admin')
    @app.route('/password',methods=['GET','POST'])
    def password_page():
        teacher()
        if session['username']!='pony':abort(403)
        if request.method=='POST':
            verify()
            with db() as c: user=c.execute('SELECT password_hash FROM users WHERE username=?',('pony',)).fetchone()
            if not check_password_hash(user['password_hash'],request.form.get('old_password','')):abort(403,'目前密碼不正確')
            password=request.form.get('new_password','')
            if not 8<=len(password)<=128 or password!=request.form.get('confirmation'):abort(400,'新密碼需 8–128 字元且確認一致')
            from teacher_password import sync_password,bank_database
            try: _,generation=sync_password(bank_database(),database(),password)
            except ValueError as error:abort(400,str(error))
            session['generation']=generation
            session.pop('token',None)
            flash('各 Lab 的 pony 密碼及 JSON 已同步')
            return redirect('/admin')
        return render_template('password.html')
    @app.post('/logout')
    def logout():
        verify();session.clear();return redirect('/login')
    @app.get('/steal')
    def steal():
        if kind!='collector':abort(404)
        with db() as c: c.execute('INSERT INTO captures(content) VALUES (?)',(request.args.get('cookie','')[:10000],))
        return '',204
    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        if kind!='xss' or session.get('mode','vulnerable')=='protected':
            response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if kind=='xss' and logged(): response.set_cookie('fake_session','XSS-CLASSROOM-ONLY',httponly=False)
        return response
    return app
