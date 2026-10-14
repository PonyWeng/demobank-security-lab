import sqlite3
from bank import create_app
from test_bank import register, login, token

def test_admin_permissions_and_reset(tmp_path):
    app = create_app({'TESTING':True, 'SECRET_KEY':'a'*32,'DATABASE':str(tmp_path/'admin.db'),'TRUSTED_HOSTS':['localhost'],'LAB_ACCESS_CODE':''})
    pony, student = app.test_client(), app.test_client()
    register(pony,'pony')
    register(student,'student')
    login(pony,'pony')
    login(student,'student')
    assert pony.get('/admin/').status_code == 403  # Name alone never grants admin.
    with sqlite3.connect(app.config['DATABASE']) as db:
        db.execute('UPDATE users SET is_admin=1 WHERE username=?',('pony',))
    assert student.get('/admin/').status_code == 403
    assert student.post('/admin/reset',data={'csrf_token':token(student),'confirmation':'RESET'}).status_code == 403
    page = pony.get('/admin/').text
    assert 'student' in page and 'DBHACKER001' in page and '管理員' in page
    assert pony.post('/admin/reset',data={'confirmation':'RESET'}).status_code == 403
    assert pony.post('/admin/reset',data={'csrf_token':token(pony,'/admin/'),'confirmation':'oops'}).status_code == 400
    assert student.post('/transfer',data={'recipient':'DBHACKER001','amount':'100'}).status_code == 302
    assert 'NT$5,100.00' in pony.get('/admin/').text
    assert pony.post('/admin/reset',data={'csrf_token':token(pony,'/admin/'),'confirmation':'RESET'}).status_code == 302
    assert pony.get('/admin/').status_code == 200
    assert student.get('/api/account').status_code == 302
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT username FROM users ORDER BY username').fetchall() == [('demo_hacker',),('pony',)]
        assert db.execute('SELECT count(*) FROM transfers').fetchone()[0] == 0
        assert db.execute('SELECT sum(balance) FROM accounts').fetchone()[0] == 1000000
    assert login(pony,'pony').status_code == 302
