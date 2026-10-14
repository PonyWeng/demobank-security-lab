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
        c.execute('CREATE TABLE IF NOT EXISTS xss_sessions(hash TEXT PRIMARY KEY,username TEXT NOT NULL,generation TEXT NOT NULL,expires INTEGER NOT NULL)')
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
        from portal_auth import identity
        if not session.get('portal_session'):return False
        user=identity(portal_path(),session['portal_session'],session.get('portal_generation'))
        if not user:return False
        with db() as c:
            generation=c.execute("SELECT value FROM settings WHERE key='generation'").fetchone()['value']
        return session.get('username') and session.get('generation')==generation
    def portal_path():
        from teacher_password import bank_database
        return app.config.get('PORTAL_DATABASE') or bank_database()
    def portal_origin():
        try:
            with sqlite3.connect(portal_path()) as c:
                row=c.execute("SELECT value FROM metadata WHERE key='public_endpoints'").fetchone()
            if row:return json.loads(row[0])['bank']
        except sqlite3.OperationalError:pass
        return 'http://bank.localhost:5000'
    def enter_from_portal():return redirect(portal_origin()+'/labs/enter/'+kind)
    def teacher():
        if not logged():abort(403,'請從課程入口登入')
        from portal_auth import identity
        u=identity(portal_path(),session['portal_session'],session['portal_generation'])
        if not u or not u['is_admin']: abort(403)
    def sign_in(user,admin=False):
        with db() as c:generation=c.execute("SELECT value FROM settings WHERE key='generation'").fetchone()['value']
        mode=session.get('mode','vulnerable');gate=session.get('gate',False)
        session.clear()
        session.update(username=user['username'],teacher=admin,generation=generation,mode=mode,gate=gate)
    def xss_user():
        import hashlib,time
        value=request.cookies.get('xss_lab_session','')
        with db() as c:
            row=c.execute('SELECT username FROM xss_sessions WHERE hash=? AND generation=? AND expires>?',(hashlib.sha256(value.encode()).hexdigest(),session.get('generation'),int(time.time()))).fetchone()
        return row['username'] if row else session['username']
    def create_xss_session(username):
        import hashlib,time
        value=secrets.token_urlsafe(32)
        with db() as c:c.execute('INSERT INTO xss_sessions VALUES (?,?,?,?)',(hashlib.sha256(value.encode()).hexdigest(),username,session['generation'],int(time.time())+7200))
        return value
    def revoke_xss_session():
        import hashlib
        with db() as c:c.execute('DELETE FROM xss_sessions WHERE hash=?',(hashlib.sha256(request.cookies.get('xss_lab_session','').encode()).hexdigest(),))
    @app.context_processor
    def helpers():
        from teacher_password import bank_database
        hub='http://bank.localhost:5000/labs'
        if bank_database().exists():
            with sqlite3.connect(bank_database()) as c:
                row=c.execute("SELECT value FROM metadata WHERE key='public_endpoints'").fetchone()
            if row:hub=json.loads(row[0])['bank']+'/labs'
        from portal_auth import identity
        user=identity(portal_path(),session.get('portal_session'),session.get('portal_generation')) if session.get('portal_session') else None
        return dict(kind=kind,token=token,hub_url=portal_origin()+'/labs',urls=urls(),mode=session.get('mode','vulnerable'),teacher=bool(logged() and user['is_admin']))
    @app.before_request
    def gate():
        host=request.host.split(':')[0]
        allowed={'localhost','127.0.0.1',f'{kind}.localhost',urlsplit(urls()[kind]).hostname}
        if host not in allowed: abort(400,'Host not configured; use localhost teacher admin first')
        if request.endpoint not in ('static','steal','auth_entry','login','register','access') and not logged():return enter_from_portal()
    @app.get('/auth/entry')
    def auth_entry():
        from portal_auth import consume
        result=consume(portal_path(),request.args.get('ticket',''),kind)
        if not result:abort(403,'登入票證無效或過期，請回課程入口重新選擇 Lab。')
        user,identifier,generation=result
        with db() as c:
            c.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,?) ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash,is_admin=excluded.is_admin',(user['username'],user['password_hash'],user['is_admin']))
        sign_in(user,bool(user['is_admin']))
        session.update(portal_session=identifier,portal_generation=generation)
        response=redirect('/')
        if kind=='xss':response.set_cookie('xss_lab_session',create_xss_session(user['username']),httponly=session.get('mode','vulnerable')=='protected',secure=app.config['SESSION_COOKIE_SECURE'],samesite='Lax',max_age=7200)
        return response
    @app.route('/access',methods=['GET','POST'])
    def access():
        return redirect(portal_origin()+'/access')
    @app.route('/register',methods=['GET','POST'])
    def register():
        return redirect(portal_origin()+'/register')
    @app.route('/login',methods=['GET','POST'])
    @app.route('/teacher/login',methods=['GET','POST'])
    def login():
        return redirect('/') if logged() else enter_from_portal()
    @app.route('/',methods=['GET','POST'])
    def index():
        if kind=='collector':
            if not logged():return enter_from_portal()
            with db() as c: rows=c.execute('SELECT * FROM captures ORDER BY id DESC LIMIT 100').fetchall()
            return render_template('collector.html',rows=rows)
        if not logged():return enter_from_portal()
        if kind=='sql' and request.method=='GET':
            with db() as c:
                tables=[]
                for name in ('users','messages','captures'):
                    if name=='users':
                        from attacks.sql_demo import connect as demo_connect
                        with demo_connect(database().with_suffix('.sql-demo.sqlite')) as demo:
                            columns=[(0,'id','INTEGER',0,None,1),(1,'username','TEXT',0,None,0),(2,'password','TEXT',0,None,0),(3,'isAdmin','INTEGER',0,None,0)]
                            data=demo.execute('SELECT * FROM users LIMIT 100').fetchall()
                    else:
                        columns=c.execute(f'PRAGMA table_info({name})').fetchall()
                        data=c.execute(f'SELECT * FROM {name} LIMIT 100').fetchall()
                    tables.append({'table':name,'columns':columns,'rows':data})
            return render_template('sql_index.html',db_info=tables,user=session['username'])
        if request.method=='POST':
            verify()
            if kind=='xss':
                content=request.form.get('content','')
                if len(content)>10000: abort(400)
                with db() as c: c.execute('INSERT INTO messages(username,content) VALUES (?,?)',(xss_user(),content))
            return redirect('/')
        with db() as c: rows=c.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 100').fetchall() if kind=='xss' else []
        return render_template('xss_board.html',messages=rows,user_id=xss_user())
    @app.route('/simulate/login',methods=['GET','POST'])
    def simulate_login():
        if kind!='sql':abort(404)
        result=None;query=''
        if request.method=='POST':
            verify()
            name=request.form.get('username','');password=request.form.get('password','')
            from attacks.sql_demo import connect as demo_connect, login as demo_login
            with demo_connect(database().with_suffix('.sql-demo.sqlite')) as c:
                try:
                    row,query=demo_login(c,name,password,session.get('mode','vulnerable')=='protected')
                    result=('模擬登入成功：'+row['username']+' · '+('假管理員' if row['isAdmin'] else '一般示範帳號')) if row else '模擬登入失敗（請回資料表查看異動）'
                except sqlite3.Error as error:
                    c.rollback()
                    result='SQL 錯誤：'+str(error)
        return render_template('simulate_login.html',result=result,query=query)
    @app.post('/simulate/reset')
    def reset_sql_demo():
        if kind!='sql':abort(404)
        teacher();verify()
        from attacks.sql_demo import connect as demo_connect
        with demo_connect(database().with_suffix('.sql-demo.sqlite')) as c:
            c.execute('DELETE FROM users')
            c.executemany('INSERT INTO users(username,password,isAdmin) VALUES (?,?,?)',[('ADMIN','admin001',1),('pony','demo001',0),('student','student001',0)])
        return redirect('/')
    @app.post('/delete_message/<int:msg_id>')
    def delete_message(msg_id):
        if kind!='xss':abort(404)
        if not logged():abort(403)
        verify()
        with db() as c:
            row=c.execute('SELECT username FROM messages WHERE id=?',(msg_id,)).fetchone()
            if not row:abort(404)
            if row['username']!=xss_user():abort(403)
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
                hashed=generate_password_hash(password)
                with sqlite3.connect(portal_path()) as c:
                    uid=c.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,?)',(name,hashed,int(request.form.get('isAdmin')=='on'))).lastrowid
                    c.execute('INSERT INTO accounts(user_id,number,balance) VALUES (?,?,500000)',(uid,'DB'+secrets.token_hex(6).upper()))
                with db() as c:c.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,?) ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash,is_admin=excluded.is_admin',(name,hashed,int(request.form.get('isAdmin')=='on')))
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
            response=redirect('/security')
            if kind=='xss':
                username=xss_user();revoke_xss_session()
                response.set_cookie('xss_lab_session',create_xss_session(username),httponly=session['mode']=='protected',secure=app.config['SESSION_COOKIE_SECURE'],samesite='Lax',max_age=7200)
            return response
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
        with sqlite3.connect(portal_path()) as c:
            c.row_factory=sqlite3.Row
            users=c.execute('SELECT username,is_admin FROM users').fetchall()
        return render_template('admin.html',users=users)
    @app.post('/admin/reset')
    def reset():
        teacher();verify()
        if request.form.get('confirmation')!='RESET':abort(400)
        with db() as c:
            c.execute('DELETE FROM messages');c.execute('DELETE FROM captures');c.execute('DELETE FROM xss_sessions');c.execute('DELETE FROM users WHERE is_admin=0')
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
            try: portal_generation,generation=sync_password(portal_path(),database(),password)
            except ValueError as error:abort(400,str(error))
            session['generation']=generation
            session['portal_generation']=portal_generation
            session.pop('token',None)
            flash('各 Lab 的 pony 密碼及 JSON 已同步')
            return redirect('/admin')
        return render_template('password.html')
    @app.post('/logout')
    def logout():
        verify()
        if kind=='xss':revoke_xss_session()
        with sqlite3.connect(portal_path()) as c:c.execute('DELETE FROM portal_sessions WHERE id=?',(session.get('portal_session'),))
        session.clear()
        response=redirect(portal_origin()+'/login')
        response.delete_cookie('xss_lab_session')
        return response
    @app.get('/steal')
    def steal():
        if kind!='collector':abort(404)
        with db() as c: c.execute('INSERT INTO captures(content) VALUES (?)',(request.args.get('cookie','')[:10000],))
        return '',204
    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def error_page(error):
        return render_template('error.html',error=error),error.code
    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        if kind!='xss' or session.get('mode','vulnerable')=='protected':
            response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response
    return app
