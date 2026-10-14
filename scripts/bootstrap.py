"""Create local configuration and initial classroom accounts without overwriting existing data."""
import json
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
from werkzeug.security import generate_password_hash
from bank import create_app
from bank.db import connect

def bootstrap(root):
    root = Path(root).resolve()
    env_path = root / '.env'
    if not env_path.exists():
        template = (root / '.env.example').read_text(encoding='utf-8')
        template = template.replace('replace-with-at-least-32-random-characters', secrets.token_urlsafe(48))
        template = template.replace('LAB_ACCESS_CODE=', 'LAB_ACCESS_CODE=' + secrets.token_urlsafe(12))
        with env_path.open('x', encoding='utf-8') as out:
            out.write(template)
        env_path.chmod(0o600)
    env = dotenv_values(env_path)
    secret = env.get('SECRET_KEY') or ''
    if secret == 'replace-with-at-least-32-random-characters' or len(secret) < 32:
        raise RuntimeError('Existing .env has no valid SECRET_KEY; update it without deleting existing configuration.')
    database = Path(env.get('DATABASE') or 'instance/demobank.sqlite')
    if not database.is_absolute():
        database = root / database
    fresh_db = not database.exists()
    app = create_app({'SECRET_KEY':secret,'DATABASE':str(database),'LAB_ACCESS_CODE':env.get('LAB_ACCESS_CODE') or ''})
    credentials_path = root / 'instance/setup-credentials.json'
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    credentials = json.loads(credentials_path.read_text(encoding='utf-8')) if credentials_path.exists() else {'accounts':{}}
    credentials['lab_access_code'] = env.get('LAB_ACCESS_CODE') or ''
    with app.app_context(), connect() as db:
        for username, number, admin in [('pony','DBADMIN001',1),('alice','DB100001',0),('bob','DB100002',0)]:
            existing = db.execute('SELECT is_admin FROM users WHERE username=?',(username,)).fetchone()
            if existing:
                if admin and not existing['is_admin']:
                    raise RuntimeError('Existing pony is not an administrator; no privilege or password changes made.')
                continue
            password = secrets.token_urlsafe(18)
            uid = db.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,?)',(username,generate_password_hash(password),admin)).lastrowid
            db.execute('INSERT INTO accounts(user_id,number,balance) VALUES (?,?,500000)',(uid,number))
            credentials['accounts'][username] = {'password':password,'account':number,'role':'admin' if admin else 'student'}
        if fresh_db:
            password = secrets.token_urlsafe(18)
            db.execute('UPDATE users SET password_hash=? WHERE username=?',(generate_password_hash(password),'demo_hacker'))
            credentials['accounts']['demo_hacker'] = {'password':password,'account':'DBHACKER001','role':'demo hacker'}
        temporary = credentials_path.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8') as out:
            json.dump(credentials,out,indent=2)
        temporary.chmod(0o600)
        os.replace(temporary,credentials_path)
    print('Configuration and accounts ready. Existing secrets, accounts, passwords and balances preserved.')
    print(f'Private initial credentials: {credentials_path}')
    return app

if __name__ == '__main__':
    bootstrap(Path(__file__).resolve().parents[1])
