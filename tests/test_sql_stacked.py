import sqlite3
import pytest
from attacks.sql_demo import connect, login

def test_four_payloads_and_protection(tmp_path):
    payloads=["ADMIN' OR 1=1 -- ","ADMIN'; INSERT INTO users(username,password,isAdmin) VALUES ('hacker','9999',1); -- ","hacker'; DELETE FROM users WHERE username='pony'; -- ","'; UPDATE users SET isAdmin=1 WHERE username='student'; -- "]
    with connect(tmp_path/'demo.sqlite') as c:
        assert login(c,payloads[0],'bad',False)[0]['isAdmin']==1
        for payload in payloads[1:]:login(c,payload,'bad',False)
        assert c.execute("SELECT password,isAdmin FROM users WHERE username='hacker'").fetchone()[:]==('9999',1)
        assert not c.execute("SELECT 1 FROM users WHERE username='pony'").fetchone()
        assert c.execute("SELECT isAdmin FROM users WHERE username='student'").fetchone()[0]==1
        assert login(c,'hacker','9999',False)[0]['username']=='hacker'
    with connect(tmp_path/'protected.sqlite') as c:
        before=[tuple(r) for r in c.execute('SELECT * FROM users')]
        for payload in payloads:assert login(c,payload,'bad',True)[0] is None
        assert before==[tuple(r) for r in c.execute('SELECT * FROM users')]
        with pytest.raises(sqlite3.DatabaseError):login(c,"ADMIN'; ATTACH DATABASE 'other.sqlite' AS portal; -- ",'bad',False)
        c.rollback()
