import re,sqlite3
import pytest
from werkzeug.security import generate_password_hash
from bank import create_app
from bank.db import connect
from attacks import lab
import teacher_password
from portal_auth import issue

@pytest.fixture
def apps(tmp_path,monkeypatch):
    monkeypatch.setenv('ATTACKS_DATABASE',str(tmp_path/'lab.sqlite'))
    monkeypatch.setenv('ATTACKS_SECRET_KEY','s'*48)
    bankpath=tmp_path/'bank.sqlite'
    monkeypatch.setattr(teacher_password,'bank_database',lambda:bankpath)
    portal=create_app({'SECRET_KEY':'p'*40,'DATABASE':str(bankpath),'LAB_ACCESS_CODE':'','TRUSTED_HOSTS':['localhost']})
    with portal.app_context(),connect() as c:
        for name,admin in [('pony',1),('alice',0)]:
            uid=c.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,?)',(name,generate_password_hash(name+'password'),admin)).lastrowid
            c.execute('INSERT INTO accounts(user_id,number,balance) VALUES (?,?,500000)',(uid,'DB'+name))
    result={k:lab.create_app(k,{'TESTING':True,'PORTAL_DATABASE':str(bankpath)}) for k in ('sql','xss','collector')}
    with lab.db() as c:
        for name,admin in [('pony',1),('alice',0)]:c.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,?)',(name,generate_password_hash(name+'password'),admin))
    return result

def token(c,path='/security'):
    return re.search('name="csrf_token"[^>]*value="([^"]+)"',c.get(path).text)[1]

def login(c,name='alice',teacher=False):
    path=c.application.config['PORTAL_DATABASE']
    with sqlite3.connect(path) as db:uid=db.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone()[0]
    ticket,_=issue(path,uid,c.application.config['SESSION_COOKIE_NAME'].removeprefix('attacks_'))
    return c.get('/auth/entry?ticket='+ticket)

def test_sql_modes(apps):
    c=apps['sql'].test_client();login(c)
    data={'csrf_token':token(c),'username':"' OR 1=1 -- ",'password':'bad'}
    assert '模擬登入成功' in c.post('/simulate/login',data=data).text
    assert c.get('/admin').status_code==403
    with c.session_transaction() as s:assert s['username']=='alice' and not s['teacher']
    c.post('/security',data={'csrf_token':token(c),'mode':'protected'})
    assert '模擬登入失敗' in c.post('/simulate/login',data={**data,'csrf_token':token(c)}).text

def test_sql_changes_reported_and_only_users_shown(apps):
    c=apps['sql'].test_client();login(c)
    def submit(payload):
        return c.post('/simulate/login',data={'csrf_token':token(c),'username':payload,'password':'bad'}).text
    assert '新增 1 位使用者：hacker' in submit("ADMIN'; INSERT INTO users(username,password,isAdmin) VALUES ('hacker','9999',1); -- ")
    assert '修改 1 位使用者：pony' in submit("'; UPDATE users SET isAdmin=1 WHERE username='pony'; -- ")
    assert '刪除 1 位使用者：pony' in submit("hacker'; DELETE FROM users WHERE username='pony'; -- ")
    assert '資料未變更' in submit("hacker'; DELETE FROM users WHERE username='missing'; -- ")
    page=c.get('/').text
    assert 'Table: users' in page and 'hacker' in page
    assert 'Table: messages' not in page and 'Table: captures' not in page
    assert '假管理員' not in page and 'Columns' not in page
    assert c.get('/admin').status_code==403

def test_xss_encoding_and_csp(apps):
    c=apps['xss'].test_client();login(c)
    payload="<script>alert('CLASSROOM')</script>"
    c.post('/',data={'csrf_token':token(c),'content':payload})
    assert payload in c.get('/').text
    c.post('/security',data={'csrf_token':token(c),'mode':'protected'})
    response=c.get('/')
    assert payload not in response.text and '&lt;script&gt;' in response.text
    assert "script-src 'self'" in response.headers['Content-Security-Policy']

def test_admin_and_reset(apps):
    c=apps['sql'].test_client();login(c,'pony')
    assert c.get('/admin').status_code==200
    assert c.post('/admin/reset',data={'confirmation':'RESET'}).status_code==403
    assert c.post('/admin/reset',data={'csrf_token':token(c,'/admin'),'confirmation':'RESET'}).status_code==302

def test_endpoints_and_collector(apps):
    c=apps['sql'].test_client();login(c,'pony')
    c.post('/admin',data={'csrf_token':token(c,'/admin'),'sql':'https://sql.test','xss':'https://xss.test','collector':'https://collector.test'})
    collector=apps['collector'].test_client()
    assert collector.get('/').status_code==302
    assert collector.get('/steal?cookie=fake_session=CLASSROOM').status_code==204
    login(collector)
    assert 'fake_session=CLASSROOM' in collector.get('/').text
    assert collector.get('/admin').status_code==403

def test_features_preserved(apps):
    sql=apps['sql'].test_client();login(sql,'pony')
    assert 'Table: users' in sql.get('/').text
    data={'csrf_token':token(sql,'/admin/users/add'),'username':'new_student','password':'student-pass-123'}
    assert 'User added successfully!' in sql.post('/admin/users/add',data=data).text
    with sqlite3.connect(sql.application.config['PORTAL_DATABASE']) as db:assert db.execute('SELECT username FROM users WHERE username=?',('new_student',)).fetchone()
    student=apps['xss'].test_client();login(student)
    student.post('/',data={'csrf_token':token(student),'content':'hello'})
    with lab.db() as db:mid=db.execute('SELECT id FROM messages').fetchone()[0]
    assert student.post(f'/delete_message/{mid}',data={'csrf_token':token(student)}).status_code==302
