import sqlite3
from bank import create_app

def test_hacker_created_once_and_reset(tmp_path):
    config = {'SECRET_KEY': 's' * 32, 'DATABASE': str(tmp_path / 'lab.db'), 'LAB_ACCESS_CODE': ''}
    app = create_app(config)
    create_app(config)
    with sqlite3.connect(config['DATABASE']) as db:
        assert db.execute('SELECT count(*) FROM users WHERE username=?', ('demo_hacker',)).fetchone()[0] == 1
        assert db.execute('SELECT balance FROM accounts WHERE number=?', ('DBHACKER001',)).fetchone()[0] == 500000
        db.execute('UPDATE accounts SET balance=510000 WHERE number=?', ('DBHACKER001',))
    create_app(config)
    assert '5,100.00' in app.test_cli_runner().invoke(args=['hacker-summary']).output
    result = app.test_cli_runner().invoke(args=['reset-lab', '--yes'])
    assert result.exit_code == 0
    assert '5,000.00' in app.test_cli_runner().invoke(args=['hacker-summary']).output
