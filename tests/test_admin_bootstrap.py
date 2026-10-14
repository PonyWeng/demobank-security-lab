from bank import create_app

def test_create_admin_cli(tmp_path):
    app=create_app({'SECRET_KEY':'s'*32,'DATABASE':str(tmp_path/'bootstrap.db'),'LAB_ACCESS_CODE':'','TRUSTED_HOSTS':['localhost']})
    runner=app.test_cli_runner()
    result=runner.invoke(args=['create-admin','--username','pony'],input='bootstrap-pass-123\nbootstrap-pass-123\n')
    assert result.exit_code==0
    from test_bank import login
    client=app.test_client()
    assert login_with_password(client).status_code==302
    assert client.get('/admin/').status_code==200
    assert runner.invoke(args=['create-admin','--username','pony'],input='new-password-123\nnew-password-123\n').exit_code!=0

def login_with_password(client):
    from test_bank import token
    return client.post('/login',data={'csrf_token':token(client,'/login'),'username':'pony','password':'bootstrap-pass-123'})
