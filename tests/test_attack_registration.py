from attacks.test_lab import apps,token,login

def test_registration_flow(apps):
    client=apps['xss'].test_client()
    result=client.post('/register',data={'csrf_token':token(client,'/register'),'username':'student','password':'short'})
    assert result.status_code==200 and '密碼需 8' in result.text
    result=client.post('/register',data={'csrf_token':token(client,'/register'),'username':'student','password':'student123'})
    assert result.status_code==302 and result.location=='/'
    assert client.get('/').status_code==200
    assert client.get('/login').location=='/'
    assert client.get('/register').location=='/'
    sql=apps['sql'].test_client()
    assert sql.post('/login',data={'csrf_token':token(sql),'username':'student','password':'student123'}).status_code==302
    collector=apps['collector'].test_client()
    assert collector.post('/register',data={'csrf_token':token(collector,'/register'),'username':'student','password':'student123'}).location=='/'
    assert collector.get('/').status_code==200
