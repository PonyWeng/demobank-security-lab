import json,sqlite3
from werkzeug.security import generate_password_hash,check_password_hash
from bank import create_app
from bank.db import connect
from teacher_password import sync_password
from test_bank import register,login,token

def test_ui_password_sync(tmp_path,monkeypatch):
    attack_path=tmp_path/'attacks'/'db.sqlite';attack_path.parent.mkdir()
    monkeypatch.setenv('ATTACKS_DATABASE',str(attack_path))
    monkeypatch.setenv('ATTACKS_SECRET_KEY','s'*32)
    monkeypatch.setenv('ATTACKS_LAB_ACCESS_CODE','')
    from attacks.lab import create_app as attacks_app
    attack=attacks_app('sql')
    with sqlite3.connect(attack_path) as db:db.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,1)',('pony',generate_password_hash('test-pass-123')))
    bank_path=tmp_path/'bank'/'db.sqlite';bank_path.parent.mkdir()
    app=create_app({'TESTING':True,'SECRET_KEY':'s'*32,'DATABASE':str(bank_path),'TRUSTED_HOSTS':['localhost'],'LAB_ACCESS_CODE':''})
    client=app.test_client();register(client,'pony')
    with app.app_context(),connect() as db:db.execute('UPDATE users SET is_admin=1 WHERE username=?',('pony',))
    login(client,'pony')
    data={'old_password':'test-pass-123','new_password':'new-teacher-123','confirmation':'new-teacher-123'}
    assert client.post('/admin/password',data=data).status_code==403
    data['csrf_token']=token(client,'/admin/password')
    assert client.post('/admin/password',data={**data,'old_password':'bad'}).status_code==403
    assert client.post('/admin/password',data=data).status_code==302
    for path in (bank_path,attack_path):
        with sqlite3.connect(path) as db:assert check_password_hash(db.execute('SELECT password_hash FROM users WHERE username=?',('pony',)).fetchone()[0],'new-teacher-123')
    assert json.loads((bank_path.parent/'setup-credentials.json').read_text())['accounts']['pony']['password']=='new-teacher-123'
    assert json.loads((attack_path.parent/'setup-credentials.json').read_text())['pony']=='new-teacher-123'
    assert client.get('/admin/').status_code==200
    import re,teacher_password
    monkeypatch.setattr(teacher_password,'bank_database',lambda:bank_path)
    attack_client=attack.test_client()
    def attack_token(path):
        return re.search('name="csrf_token"[^>]*value="([^"]+)"',attack_client.get(path).text)[1]
    assert attack_client.post('/teacher/login',data={'csrf_token':attack_token('/teacher/login'),'username':'pony','password':'new-teacher-123'}).status_code==302
    assert attack_client.post('/password',data={'csrf_token':attack_token('/password'),'old_password':'new-teacher-123','new_password':'final-teacher-123','confirmation':'final-teacher-123'}).status_code==302
    for path in (bank_path,attack_path):
        with sqlite3.connect(path) as db:assert check_password_hash(db.execute('SELECT password_hash FROM users WHERE username=?',('pony',)).fetchone()[0],'final-teacher-123')
    assert client.get('/admin/').status_code==302
