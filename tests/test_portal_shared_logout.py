from attacks.test_lab import apps,token
from portal_auth import issue
import sqlite3

def test_one_portal_session_logout_revokes_all_labs(apps):
    path=apps['sql'].config['PORTAL_DATABASE']
    with sqlite3.connect(path) as c:uid=c.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
    first,sid=issue(path,uid,'sql')
    second,_=issue(path,uid,'xss',sid)
    sql=apps['sql'].test_client();xss=apps['xss'].test_client()
    sql.get('/auth/entry?ticket='+first);xss.get('/auth/entry?ticket='+second)
    assert xss.get('/').status_code==200
    sql.post('/logout',data={'csrf_token':token(sql)})
    assert xss.get('/').status_code==302
