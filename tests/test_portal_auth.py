import time,sqlite3,hashlib
from attacks.test_lab import apps,login,token
from portal_auth import issue,consume

def test_ticket_binding_replay_expiration(apps):
    path=apps['sql'].config['PORTAL_DATABASE']
    with sqlite3.connect(path) as db:uid=db.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
    ticket,sid=issue(path,uid,'sql')
    assert consume(path,ticket,'xss') is None
    assert consume(path,ticket,'sql')[0]['username']=='alice'
    assert consume(path,ticket,'sql') is None
    expired,_=issue(path,uid,'sql',sid)
    with sqlite3.connect(path) as db:db.execute('UPDATE handoffs SET expires=0 WHERE hash=?',(hashlib.sha256(expired.encode()).hexdigest(),))
    assert consume(path,expired,'sql') is None

def test_common_logout_and_single_register(apps):
    sql=apps['sql'].test_client();xss=apps['xss'].test_client()
    login(sql);login(xss)
    assert sql.get('/register').status_code==302
    assert '/register' in sql.get('/register').location
    assert sql.get('/teacher/login').location=='/'
    sql.post('/logout',data={'csrf_token':token(sql)})
    # Separate central sessions remain isolated; revoked session cannot be reused.
    assert sql.get('/').status_code==302
    assert xss.get('/').status_code==200
