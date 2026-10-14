import re
import pytest
from werkzeug.security import generate_password_hash
from attacks import lab

@pytest.fixture
def apps(tmp_path,monkeypatch):
    monkeypatch.setenv('ATTACKS_DATABASE',str(tmp_path/'lab.sqlite'))
    monkeypatch.setenv('ATTACKS_SECRET_KEY','s'*48)
    monkeypatch.setenv('ATTACKS_LAB_ACCESS_CODE','')
    apps={k:lab.create_app(k,{'TESTING':True}) for k in ('sql','xss','collector')}
    with lab.db() as c:
        for name,admin in [('pony',1),('alice',0)]:
            c.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,?)',(name,generate_password_hash(name+'password'),admin))
    return apps

def token(c,path='/login'):
    return re.search('name="csrf_token"[^>]*value="([^"]+)"',c.get(path).text)[1]

def test_original_features(apps):
    sql=apps['sql'].test_client();login(sql,'pony')
    page=sql.get('/').text
    assert 'Database Structure &amp; Data' in page or 'Database Structure & Data' in page
    assert 'Table: users' in page and 'password_hash' in page and 'Add new User' in page
    data={'csrf_token':token(sql,'/admin/users/add'),'username':'new_student','password':'student-pass-123'}
    assert 'User added successfully!' in sql.post('/admin/users/add',data=data).text
    student=apps['xss'].test_client();login(student)
    assert student.get('/admin/users/add').status_code==403
    student.post('/',data={'csrf_token':token(student,'/security'),'content':'hello'})
    with lab.db() as c:mid=c.execute('SELECT id FROM messages').fetchone()[0]
    assert 'xss_board.css' in student.get('/').text
    assert student.post(f'/delete_message/{mid}',data={'csrf_token':token(student,'/security')}).status_code==302

def login(c,name='alice',teacher=False):
    path='/teacher/login' if teacher else '/login'
    return c.post(path,data={'csrf_token':token(c,path),'username':name,'password':name+'password'})

def test_sql_modes(apps):
    c=apps['sql'].test_client()
    assert c.post('/login',data={'csrf_token':token(c),'username':"' OR 1=1 -- ",'password':'bad'}).status_code==302
    assert c.get('/admin').status_code==403
    c.post('/security',data={'csrf_token':token(c,'/security'),'mode':'protected'})
    c.post('/logout',data={'csrf_token':token(c,'/security')})
    c.post('/security',data={'csrf_token':token(c,'/security'),'mode':'protected'})
    assert c.post('/login',data={'csrf_token':token(c),'username':"' OR 1=1 -- ",'password':'bad'}).status_code==200
    assert login(c).status_code==302

def test_xss_encoding_and_csp(apps):
    c=apps['xss'].test_client();login(c)
    payload="<script>alert('CLASSROOM')</script>"
    c.post('/',data={'csrf_token':token(c,'/security'),'content':payload})
    assert payload in c.get('/').text
    assert 'Content-Security-Policy' not in c.get('/').headers
    c.post('/security',data={'csrf_token':token(c,'/security'),'mode':'protected'})
    response=c.get('/')
    assert payload not in response.text and '&lt;script&gt;' in response.text
    assert "script-src 'self'" in response.headers['Content-Security-Policy']

def test_admin_and_reset(apps):
    c=apps['sql'].test_client();login(c,'pony',True)
    assert c.get('/admin').status_code==200
    assert c.post('/admin/reset',data={'confirmation':'RESET'}).status_code==403
    assert c.post('/admin/reset',data={'csrf_token':token(c,'/admin'),'confirmation':'RESET'}).status_code==302
    with lab.db() as db: assert [r['username'] for r in db.execute('SELECT username FROM users')]==['pony']

def test_endpoints_and_collector(apps):
    c=apps['sql'].test_client();login(c,'pony',True)
    c.post('/admin',data={'csrf_token':token(c,'/admin'),'sql':'https://sql.test','xss':'https://xss.test','collector':'https://collector.test'})
    assert apps['xss'].test_client().get('/login',base_url='https://xss.test').status_code==200
    collector=apps['collector'].test_client()
    assert collector.get('/').status_code==403
    assert collector.get('/steal?cookie=fake_session=CLASSROOM').status_code==204
    login(collector,'pony',True)
    assert 'fake_session=CLASSROOM' in collector.get('/').text
