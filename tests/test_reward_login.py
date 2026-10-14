from bank import create_app
from test_bank import register, login, token

def test_reward_login_flow(tmp_path):
    app = create_app({'TESTING': True, 'DEFAULT_CSRF_MODE': 'protected', 'SECRET_KEY': 'x'*32, 'DATABASE': str(tmp_path/'bank.db'), 'TRUSTED_HOSTS': ['localhost'], 'LAB_ACCESS_CODE': ''})
    client = app.test_client()
    register(client, 'student')
    client.post('/logout',data={'csrf_token':token(client,'/bank')})
    result = client.post('/transfer?reward=1', data={'recipient':'DBHACKER001','amount':'100'})
    assert result.status_code == 401
    assert '系統將自動跳轉' in result.text
    page = client.get('/login?reward=1')
    assert '請先登入 DemoBank' in page.text
    result = client.post('/login?reward=1', data={'csrf_token': token(client,'/login?reward=1'), 'username':'student','password':'test-pass-123'})
    assert result.location == '/reward-return'
    assert app.config['PLAYGROUND_URL'] in client.get('/reward-return').text
    assert client.get('/api/account').json['account']['balance'] == 500000
    assert client.post('/transfer?reward=1',data={'recipient':'DBHACKER001','amount':'100'}).status_code == 403
    assert client.post('/login?reward=1&next=https://evil.example', data={'csrf_token':token(client,'/login'), 'username':'student','password':'test-pass-123'}).location == '/reward-return'
