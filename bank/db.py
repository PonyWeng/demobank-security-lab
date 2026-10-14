import sqlite3
import click
from contextlib import contextmanager
from flask import current_app
from werkzeug.security import generate_password_hash
from .demo import HACKER_USERNAME, HACKER_ACCOUNT

def ensure_hacker(db):
    import secrets
    user = db.execute('SELECT id FROM users WHERE username=?', (HACKER_USERNAME,)).fetchone()
    if user:
        account = db.execute('SELECT number FROM accounts WHERE user_id=?', (user['id'],)).fetchone()
        if not account or account['number'] != HACKER_ACCOUNT:
            raise RuntimeError('Reserved demo_hacker username conflicts with an existing account')
        return
    uid = db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)', (HACKER_USERNAME, generate_password_hash(secrets.token_urlsafe(48)))).lastrowid
    db.execute('INSERT INTO accounts(user_id,number,balance) VALUES (?,?,500000)', (uid, HACKER_ACCOUNT))

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE NOT NULL REFERENCES users(id), number TEXT UNIQUE NOT NULL, balance INTEGER NOT NULL CHECK(balance >= 0));
CREATE TABLE IF NOT EXISTS transfers(id INTEGER PRIMARY KEY, sender INTEGER NOT NULL REFERENCES accounts(id), recipient INTEGER NOT NULL REFERENCES accounts(id), amount INTEGER NOT NULL CHECK(amount > 0), created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''

@contextmanager
def connect():
    db = sqlite3.connect(current_app.config['DATABASE'], timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()

def init_db():
    import secrets
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript(SCHEMA)
        from portal_auth import initialize
        initialize(db)
        if 'is_admin' not in {row['name'] for row in db.execute('PRAGMA table_info(users)')}:
            db.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0 CHECK(is_admin IN (0,1))')
        db.execute("INSERT OR IGNORE INTO metadata VALUES ('generation', ?)", (secrets.token_hex(16),))
        ensure_hacker(db)

def reset_system(db):
    import secrets
    db.execute('BEGIN IMMEDIATE')
    db.execute('DELETE FROM transfers')
    db.execute('DELETE FROM accounts WHERE user_id IN (SELECT id FROM users WHERE is_admin=0 AND username<>?)', (HACKER_USERNAME,))
    db.execute('DELETE FROM users WHERE is_admin=0 AND username<>?', (HACKER_USERNAME,))
    db.execute('UPDATE accounts SET balance=500000')
    generation = secrets.token_hex(16)
    db.execute("UPDATE metadata SET value=? WHERE key='generation'", (generation,))
    ensure_hacker(db)
    return generation

def register_cli(app):
    @app.cli.command('create-admin')
    @click.option('--username', default='pony', show_default=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(username, password):
        import re
        import secrets
        if not re.fullmatch(r'[A-Za-z0-9_]{3,32}', username) or username.casefold() == HACKER_USERNAME.casefold() or not 8 <= len(password) <= 128:
            raise click.ClickException('Invalid username or password (8–128 characters required)')
        with connect() as db:
            if db.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone():
                raise click.ClickException('User already exists; existing passwords and roles unchanged')
            uid=db.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,1)',(username,generate_password_hash(password))).lastrowid
            db.execute('INSERT INTO accounts(user_id,number,balance) VALUES (?,?,500000)',(uid,'DB'+secrets.token_hex(6).upper()))
        click.echo(f'Administrator {username} created.')
    @app.cli.command('reset-lab')
    @click.option('--yes', is_flag=True, help='Confirm deletion of all fictional accounts')
    def reset(yes):
        import secrets
        if not yes:
            raise click.ClickException('Use --yes to confirm deletion')
        with connect() as db:
            reset_system(db)
        click.echo('Student accounts removed; transactions cleared; admin and hacker accounts preserved with NT$5,000; sessions invalidated.')
    @app.cli.command('hacker-summary')
    def hacker_summary():
        with connect() as db:
            account = db.execute('SELECT id,balance FROM accounts WHERE number=?', (HACKER_ACCOUNT,)).fetchone()
            rows = db.execute('SELECT t.amount,t.created_at,a.number FROM transfers t JOIN accounts a ON a.id=t.sender WHERE t.recipient=? ORDER BY t.id DESC LIMIT 20', (account['id'],)).fetchall()
        click.echo(f'{HACKER_ACCOUNT}: NT${account["balance"] / 100:,.2f}')
        for row in rows:
            from lab_time import taipei_time
            click.echo(f'{taipei_time(row["created_at"])} | {row["number"]} | +NT${row["amount"] / 100:,.2f}')
    @app.cli.command('seed-lab')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def seed(password):
        if len(password) < 8:
            raise click.ClickException('Password must contain at least 8 characters')
        with connect() as db:
            for name, number in [('alice', 'DB100001'), ('bob', 'DB100002')]:
                if db.execute('SELECT id FROM users WHERE username=?', (name,)).fetchone():
                    continue
                uid = db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)', (name, generate_password_hash(password))).lastrowid
                db.execute('INSERT INTO accounts(user_id,number,balance) VALUES (?,?,500000)', (uid, number))
        click.echo('alice / DB100001 and bob / DB100002 ready (existing accounts preserved).')
