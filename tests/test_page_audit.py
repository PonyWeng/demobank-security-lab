import os,re,json,threading
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
from werkzeug.security import generate_password_hash
from bank import create_app
from bank.db import connect
from attacks import lab
import attacker,teacher_password

def test_all_page_layouts(tmp_path,monkeypatch):
    bank_path=tmp_path/'bank.sqlite'
    monkeypatch.setenv('ATTACKS_DATABASE',str(tmp_path/'attacks.sqlite'))
    monkeypatch.setenv('ATTACKS_SECRET_KEY','a'*40)
    monkeypatch.setenv('ATTACKS_LAB_ACCESS_CODE','')
    monkeypatch.setattr(teacher_password,'bank_database',lambda:bank_path)
    bank=create_app({'SECRET_KEY':'b'*40,'DATABASE':str(bank_path),'LAB_ACCESS_CODE':'','TRUSTED_HOSTS':['127.0.0.1'],'SESSION_COOKIE_SECURE':False,'SESSION_COOKIE_SAMESITE':'Lax'})
    origins={name:f'http://127.0.0.1:{port}' for name,port in [('bank',5250),('playground',5251),('sql',5252),('xss',5253),('collector',5254)]}
    with bank.app_context(),connect() as db:
        uid=db.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,1)',('pony',generate_password_hash('ponypony'))).lastrowid
        db.execute('INSERT INTO accounts(user_id,number,balance) VALUES (?,?,500000)',(uid,'DBAUDIT001'))
        db.execute("INSERT INTO metadata VALUES ('public_endpoints',?)",(json.dumps({'bank':origins['bank'],'playground':origins['playground']+'/playground','cross_site':False}),))
    apps={'bank':bank,'playground':attacker.app,**{name:lab.create_app(name) for name in ['sql','xss','collector']}}
    with lab.db() as db:
        db.execute('INSERT INTO users(username,password_hash,is_admin) VALUES (?,?,1)',('pony',generate_password_hash('ponypony')))
        db.execute("INSERT INTO settings VALUES ('urls',?)",(json.dumps({k:origins[k] for k in ['sql','xss','collector']}),))
    monkeypatch.setitem(attacker.app.config,'ENDPOINT_PROVIDER',lambda:origins['bank'])
    servers=[make_server('127.0.0.1',urlsplit(origins[name]).port,app,threaded=True) for name,app in apps.items()]
    for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel=os.getenv('BROWSER_CHANNEL') or None)
            ctx=browser.new_context()
            for name in ['bank','sql','xss','collector']:
                route='/login' if name=='bank' else '/teacher/login'
                html=ctx.request.get(origins[name]+route).text()
                token=re.search('name="csrf_token"[^>]*value="([^"]+)"',html)[1]
                assert ctx.request.post(origins[name]+route,form={'username':'pony','password':'ponypony','csrf_token':token}).ok
            paths={'bank':['/labs','/login','/register','/access','/','/lab','/admin/','/admin/password'],
                   'playground':['/playground'],
                   'sql':['/login','/teacher/login','/register','/','/security','/admin','/admin/users/add','/password'],
                   'xss':['/login','/teacher/login','/register','/','/security','/admin','/password'],
                   'collector':['/login','/teacher/login','/register','/','/security','/admin','/password']}
            page=ctx.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('response',lambda response:errors.append(f'CSS failure {response.url}') if '.css' in response.url and response.status>=400 else None)
            output=Path('test-results/page-audit');output.mkdir(parents=True,exist_ok=True)
            audited=[]
            for kind,routes in paths.items():
                for route in routes:
                    page.set_viewport_size({'width':1280,'height':900})
                    response=page.goto(origins[kind]+route)
                    assert response.status==200,(kind,route,response.status)
                    assert page.locator('link[rel=stylesheet]').count()>0
                    if kind in ['sql','xss'] and route in ['/login','/teacher/login']:
                        parent='.login-box' if kind=='sql' else '.login-container'
                        assert page.locator(parent+' .lab-links').count()==1
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(kind,route,'mobile overflow')
                    page.screenshot(path=str(output/(kind+'-'+(route.strip('/').replace('/','-') or 'home')+'.png')),full_page=True)
                    audited.append(kind+route)
            assert not errors,errors
            (output/'report.json').write_text(json.dumps(audited,indent=2),encoding='utf-8')
            browser.close()
    finally:
        for server in servers:server.shutdown();server.server_close()
