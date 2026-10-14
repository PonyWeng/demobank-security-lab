import json,secrets
from pathlib import Path
from werkzeug.security import generate_password_hash
from lab import ROOT,create_app,db

env=ROOT/'.env'
if not env.exists():
    env.write_text((ROOT/'.env.example').read_text().replace('replace-with-random-secret',secrets.token_urlsafe(48)),encoding='utf-8')
    env.chmod(0o600)
from dotenv import load_dotenv
load_dotenv(env,override=True)
app=create_app('sql')
path=ROOT/'instance/setup-credentials.json'
credentials=json.loads(path.read_text()) if path.exists() else {}
with db() as c:
    for name,password,admin in [('pony','ponypony',1),('alice','alice001',0),('bob','bob00100',0)]:
        if not c.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone():
            c.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,?)',(name,generate_password_hash(password),admin))
            credentials[name]=password
path.write_text(json.dumps(credentials,indent=2),encoding='utf-8');path.chmod(0o600)
print('Setup ready; existing accounts preserved. Initial credentials: instance/setup-credentials.json')
