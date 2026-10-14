"""Disposable SQL injection database; never connects to course identities."""
import sqlite3

def connect(path):
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE COLLATE NOCASE, password TEXT, isAdmin INTEGER DEFAULT 0)')
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='seeded'").fetchone():
        c.executemany('INSERT INTO users(username,password,isAdmin) VALUES (?,?,?)', [('ADMIN','admin001',1),('pony','demo001',0),('student','student001',0)])
        c.execute('CREATE TABLE seeded(done INTEGER)')
        c.commit()
    def authorize(action, arg1, arg2, database, trigger):
        if action in (sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW, sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_INDEX):return sqlite3.SQLITE_DENY
        if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA):return sqlite3.SQLITE_DENY
        if action in (sqlite3.SQLITE_READ, sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) and arg1!='users':return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and arg2 == 'load_extension':return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    c.set_authorizer(authorize)
    return c

def login(c, name, password, protected):
    if protected:
        query='SELECT * FROM users WHERE username=? AND password=?'
        row=c.execute(query,(name,password)).fetchone()
    else:
        query=f"SELECT * FROM users WHERE username='{name}' AND password='{password}'"
        # executescript deliberately allows stacked statements in this disposable DB.
        c.executescript('BEGIN;\n'+query+'\n;\nCOMMIT;')
        row=c.execute(query.split(';',1)[0]).fetchone()
    return row, query
