import json
import shutil
from pathlib import Path
from scripts.bootstrap import bootstrap
from bank.db import connect
from werkzeug.security import check_password_hash

def test_setup_idempotent(tmp_path):
    shutil.copyfile(Path('.env.example'),tmp_path/'.env.example')
    app=bootstrap(tmp_path)
    secret=(tmp_path/'.env').read_text()
    creds=json.loads((tmp_path/'instance/setup-credentials.json').read_text())
    assert set(creds['accounts'])=={'pony','alice','bob','demo_hacker'}
    assert creds['lab_access_code']
    with app.app_context(),connect() as db:
        for name,data in creds['accounts'].items():
            row=db.execute('SELECT password_hash,is_admin FROM users WHERE username=?',(name,)).fetchone()
            assert check_password_hash(row['password_hash'],data['password'])
            assert bool(row['is_admin'])==(name=='pony')
        db.execute('UPDATE accounts SET balance=123456 WHERE number=?',('DB100001',))
    bootstrap(tmp_path)
    assert (tmp_path/'.env').read_text()==secret
    assert json.loads((tmp_path/'instance/setup-credentials.json').read_text())==creds
    with app.app_context(),connect() as db:
        assert db.execute('SELECT count(*) FROM users').fetchone()[0]==4
        assert db.execute('SELECT balance FROM accounts WHERE number=?',('DB100001',)).fetchone()[0]==123456
