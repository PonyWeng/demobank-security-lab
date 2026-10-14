import sqlite3
from bank import create_app
from test_bank import register,login,token
import attacker

def test_endpoint_settings(tmp_path):
    cfg={'TESTING':True,'SECRET_KEY':'s'*32,'DATABASE':str(tmp_path/'lab.db'),'TRUSTED_HOSTS':['localhost'],'LAB_ACCESS_CODE':''}
    app=create_app(cfg)
    client=app.test_client()
    register(client,'pony')
    login(client,'pony')
    data={'bank':'https://bank-one.trycloudflare.com','playground':'https://play-two.trycloudflare.com','cross_site':'on'}
    assert client.post('/admin/endpoints',data=data).status_code==403
    with sqlite3.connect(cfg['DATABASE']) as db:
        db.execute('UPDATE users SET is_admin=1 WHERE username=?',('pony',))
    assert client.post('/admin/endpoints',data=data).status_code==403
    data['csrf_token']=token(client,'/admin/')
    assert client.post('/admin/endpoints',data={**data,'bank':'https://bank-one.trycloudflare.com/path'}).status_code==400
    assert client.post('/admin/endpoints',data={**data,'bank':'http://bank-one.trycloudflare.com'}).status_code==400
    assert client.post('/admin/endpoints',data=data).status_code==302
    assert 'bank-one.trycloudflare.com' in client.get('/admin/').text
    public=client.get('/login',base_url=data['bank'])
    assert public.status_code==200
    assert 'SameSite=None' in public.headers['Set-Cookie'] and 'Secure;' in public.headers['Set-Cookie']
    assert client.get('/login',base_url='https://unknown.trycloudflare.com').status_code==400
    assert client.get('/admin/').status_code==200
    restarted=create_app(cfg)
    with restarted.app_context():
        from bank.endpoints import endpoints
        assert endpoints()['bank']==data['bank']
    def provider():
        with app.app_context():
            return endpoints()['bank']
    attacker.app.config['ENDPOINT_PROVIDER']=provider
    try:
        response=attacker.app.test_client().get('/playground')
        assert data['bank']+'/transfer' in response.text
        assert data['bank'] in response.headers['Content-Security-Policy']
    finally:
        attacker.app.config.pop('ENDPOINT_PROVIDER',None)
