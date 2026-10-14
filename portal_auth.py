"""One-use, short-lived, audience-bound server-side handoff tickets."""
import hashlib,secrets,sqlite3,time
from teacher_password import bank_database

def initialize(connection):
    connection.executescript('''CREATE TABLE IF NOT EXISTS portal_sessions(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS handoffs(hash TEXT PRIMARY KEY,session_id TEXT NOT NULL,target TEXT NOT NULL,expires INTEGER NOT NULL,generation TEXT NOT NULL);''')

def create_login(connection,uid):
    identifier=secrets.token_urlsafe(32)
    connection.execute('INSERT INTO portal_sessions VALUES (?,?)',(identifier,uid))
    return identifier

def issue(path,uid,target,session_id=None):
    if target not in ('sql','xss','collector'):raise ValueError('Invalid Lab')
    with sqlite3.connect(path) as c:
        initialize(c)
        if not session_id or not c.execute('SELECT 1 FROM portal_sessions WHERE id=? AND user_id=?',(session_id,uid)).fetchone():session_id=create_login(c,uid)
        generation=c.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0]
        ticket=secrets.token_urlsafe(32)
        c.execute('DELETE FROM handoffs WHERE expires<?',(int(time.time()),))
        c.execute('INSERT INTO handoffs VALUES (?,?,?,?,?)',(hashlib.sha256(ticket.encode()).hexdigest(),session_id,target,int(time.time())+60,generation))
    return ticket,session_id

def identity(path,session_id,generation):
    try:
        with sqlite3.connect(path) as c:
            c.row_factory=sqlite3.Row
            row=c.execute("SELECT u.* FROM portal_sessions p JOIN users u ON u.id=p.user_id WHERE p.id=? AND EXISTS (SELECT 1 FROM metadata WHERE key='generation' AND value=?)",(session_id,generation)).fetchone()
            return dict(row) if row else None
    except sqlite3.OperationalError:return None

def consume(path,ticket,target):
    with sqlite3.connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT session_id,target,expires,generation FROM handoffs WHERE hash=?',(hashlib.sha256(ticket.encode()).hexdigest(),)).fetchone()
        if not row or row[1]!=target or row[2]<time.time():return None
        c.execute('DELETE FROM handoffs WHERE hash=?',(hashlib.sha256(ticket.encode()).hexdigest(),))
    user=identity(path,row[0],row[3])
    return (user,row[0],row[3]) if user else None
