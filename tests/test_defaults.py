from bank import create_app
from bank.security import settings
from test_bank import register, login

def test_classroom_vulnerable_default(tmp_path):
    app = create_app({'SECRET_KEY':'s'*32, 'DATABASE':str(tmp_path/'default.db'), 'LAB_ACCESS_CODE':'', 'TRUSTED_HOSTS':['localhost']})
    assert app.config['DEFAULT_CSRF_MODE'] == 'vulnerable'
    client = app.test_client()
    register(client, 'student')
    login(client, 'student')
    with client.session_transaction() as session:
        assert 'csrf_mode' not in session
    page = client.get('/lab').text
    assert 'value="vulnerable" selected' in page
    assert client.post('/transfer', data={'recipient':'DBHACKER001','amount':'100'}, headers={'Origin':'http://evil.bank.localhost:5001'}).status_code == 302
