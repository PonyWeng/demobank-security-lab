"""One-time import of legacy Attacks students into the central course account store."""
import sys,sqlite3,secrets
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bank import create_app
from bank.db import connect
from attacks.lab import database

with create_app().app_context(),connect() as c:
    if not c.execute("SELECT 1 FROM metadata WHERE key='portal_migration_v1'").fetchone():
        if database().exists():
            with sqlite3.connect(database()) as old:
                for name,hashed in old.execute('SELECT username,password_hash FROM users'):
                    if not c.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone():
                        uid=c.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,0)',(name,hashed)).lastrowid
                        c.execute('INSERT INTO accounts(user_id,number,balance) VALUES (?,?,500000)',(uid,'DB'+secrets.token_hex(6).upper()))
        c.execute("INSERT INTO metadata VALUES ('portal_migration_v1','done')")
print('Central account migration ready; existing portal passwords and roles preserved.')
