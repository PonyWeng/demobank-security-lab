import json
import os
import threading
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
from bank import create_app
import attacker

@pytest.mark.parametrize('policy,secure,domain', [('Lax', False, 'lab.test'), ('Strict', False, 'lab.test'), ('None', True, 'lab.test'), ('Lax', False, 'localhost')])
def test_real_browser_sites(tmp_path, policy, secure, domain):
    scheme = 'https' if secure else 'http'
    bank_host = f'bank.{domain}'
    bank_url = f'{scheme}://{bank_host}:5100'
    evil_same = f'{scheme}://evil.bank.{domain}:5101'
    evil_cross = f'{scheme}://attacker.other.test:5101'
    app = create_app({'SECRET_KEY': 'browser-test-' * 4, 'DATABASE': str(tmp_path / 'browser.db'), 'BANK_ORIGIN': bank_url, 'TRUSTED_HOSTS': [bank_host], 'LAB_ACCESS_CODE': '', 'SESSION_COOKIE_SAMESITE': policy, 'SESSION_COOKIE_SECURE': secure})
    attacker.TARGET = bank_url
    app.config['PLAYGROUND_URL'] = evil_same + '/playground'
    servers = [make_server('127.0.0.1', 5100, app, ssl_context='adhoc' if secure else None, threaded=True), make_server('127.0.0.1', 5101, attacker.app, ssl_context='adhoc' if secure else None, threaded=True)]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    observations = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=os.getenv('BROWSER_CHANNEL') or None, args=['--no-proxy-server', '--host-resolver-rules=MAP *.test 127.0.0.1'])
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            dialogs = []
            def accept_dialog(dialog):
                dialogs.append(dialog.message)
                dialog.accept()
            page.on('dialog', accept_dialog)
            for name in ['alice', 'bob']:
                page.goto(bank_url + '/register')
                page.locator('[name=username]').fill(name)
                page.locator('[name=password]').fill('test-pass-123')
                page.get_by_role('button', name='建立帳戶').click()
            page.goto(bank_url + '/login')
            page.get_by_role('button', name='登出', exact=True).click()
            page.goto(evil_same + '/playground')
            assert page.locator('textarea').count() == 0
            page.get_by_role('button', name='領取活動獎勵', exact=True).click()
            page.wait_for_url(bank_url + '/login?reward=1')
            assert any('尚未登入，無法領獎' in message for message in dialogs)
            assert '請先登入 DemoBank' in page.content()
            page.locator('[name=username]').fill('alice')
            page.locator('[name=password]').fill('test-pass-123')
            page.get_by_role('button', name='登入', exact=True).click()
            page.wait_for_url(evil_same + '/playground')
            page.goto(bank_url + '/bank')
            assert page.evaluate("fetch('/api/account').then(r => r.json())")['account']['balance'] == 500000
            page.get_by_role('button', name='登出', exact=True).click()
            page.goto(bank_url + '/login')
            page.locator('[name=username]').fill('bob')
            page.locator('[name=password]').fill('test-pass-123')
            page.get_by_role('button', name='登入', exact=True).click()
            page.goto(bank_url + '/bank')
            recipient = page.locator('[data-copy]').get_attribute('data-copy')
            page.get_by_role('button', name='登出', exact=True).click()
            page.locator('[name=username]').fill('alice')
            page.locator('[name=password]').fill('test-pass-123')
            page.get_by_role('button', name='登入', exact=True).click()
            page.goto(bank_url + '/bank')
            page.locator('[name=recipient]').fill(recipient)
            page.locator('[name=amount]').fill('25')
            page.get_by_role('button', name='確認轉帳').click()
            page.goto(bank_url + '/lab')
            page.locator('[name=mode]').select_option('vulnerable')
            page.get_by_role('button', name='套用實驗設定').click()
            for source, expected_cookie in [(evil_same, True), (evil_cross, policy == 'None')]:
                page.goto(source + '/legacy-form')
                page.locator('[name=recipient]').fill(recipient)
                with page.expect_response(lambda r: r.url.split('?')[0] == bank_url + '/transfer') as pending:
                    page.get_by_role('button', name='發送偽造轉帳').click()
                response = pending.value
                headers = response.request.all_headers()
                has_cookie = 'demobank_session=' in headers.get('cookie', '')
                assert has_cookie == expected_cookie
                assert response.status == (302 if expected_cookie else 401)
                if expected_cookie:
                    assert response.headers['location'] == '/bank'
                observations.append({'policy': policy, 'source': source, 'cookie_present': has_cookie, 'origin': headers.get('origin'), 'sec_fetch_site': headers.get('sec-fetch-site'), 'status': response.status, 'location': response.headers.get('location')})
                page.goto(bank_url + '/bank')
            page.goto(bank_url + '/lab')
            page.locator('[name=mode]').select_option('protected')
            page.get_by_role('button', name='套用實驗設定').click()
            page.goto(evil_same + '/legacy-form')
            page.locator('[name=recipient]').fill(recipient)
            with page.expect_response(lambda r: r.url.split('?')[0] == bank_url + '/transfer') as pending:
                page.get_by_role('button', name='發送偽造轉帳').click()
            assert pending.value.status == 403
            page.goto(bank_url + '/bank')
            data = page.evaluate("fetch('/api/account').then(r => r.json())")
            expected_balance = 500000 - 2500 - 10000 * (1 + int(policy == 'None'))
            assert data['account']['balance'] == expected_balance
            assert len(data['transactions']) == 2 + int(policy == 'None')
            page.goto(bank_url + '/lab')
            page.locator('[name=mode]').select_option('vulnerable')
            page.get_by_role('button', name='套用實驗設定').click()
            page.goto(evil_same + '/playground')
            assert not page.locator('details').get_attribute('open')
            page.locator('summary').click()
            assert page.locator('textarea').count() == 0
            page.locator('#reward-form [name=recipient]').evaluate('(el, value) => el.value = value', recipient)
            page.locator('#reward-form [name=amount]').evaluate("el => el.value = '73'")
            if domain == 'localhost':
                page.screenshot(path='test-results/playground.png', full_page=True)
            with page.expect_response(lambda r: r.url.split('?')[0] == bank_url + '/transfer') as pending:
                page.get_by_role('button', name='領取活動獎勵', exact=True).click()
            assert pending.value.status == 303
            assert pending.value.request.all_headers()['origin'] == evil_same
            page.goto(bank_url + '/bank')
            data = page.evaluate("fetch('/api/account').then(r => r.json())")
            assert data['account']['balance'] == expected_balance - 7300
            # Same editor payload must fail after switching protection on.
            page.goto(bank_url + '/lab')
            page.locator('[name=mode]').select_option('protected')
            page.get_by_role('button', name='套用實驗設定').click()
            page.goto(evil_same + '/playground')
            assert not page.locator('details').get_attribute('open')
            page.locator('summary').click()
            page.locator('#reward-form [name=recipient]').evaluate('(el, value) => el.value = value', recipient)
            page.locator('#reward-form [name=amount]').evaluate("el => el.value = '73'")
            with page.expect_response(lambda r: r.url.split('?')[0] == bank_url + '/transfer') as pending:
                page.get_by_role('button', name='領取活動獎勵', exact=True).click()
            assert pending.value.status == 403
            page.goto(bank_url + '/bank')
            assert page.evaluate("fetch('/api/account').then(r => r.json())")['account']['balance'] == expected_balance - 7300
            page.goto(bank_url + '/lab')
            page.locator('[name=mode]').select_option('vulnerable')
            page.get_by_role('button', name='套用實驗設定').click()
            page.goto(evil_same + '/playground')
            assert not page.locator('details').get_attribute('open')
            page.locator('summary').click()
            assert page.locator('#reward-form [name=recipient]').input_value() == 'DBHACKER001'
            with page.expect_response(lambda r: r.url.split('?')[0] == bank_url + '/transfer') as pending:
                page.get_by_role('button', name='領取活動獎勵', exact=True).click()
            assert pending.value.status == 303
            page.wait_for_function("document.querySelector('.hero p')?.textContent.includes('領取成功')")
            assert page.url.startswith(evil_same + '/playground')
            assert any('請至帳戶確認已領取的獎勵金' in message for message in dialogs)
            page.goto(bank_url + '/bank')
            assert page.evaluate("fetch('/api/account').then(r => r.json())")['account']['balance'] == expected_balance - 17300
            from bank.db import connect
            with app.app_context(), connect() as db:
                assert db.execute('SELECT balance FROM accounts WHERE number=?', ('DBHACKER001',)).fetchone()['balance'] == 510000
            page.goto(bank_url + '/lab')
            page.locator('[name=mode]').select_option('protected')
            page.get_by_role('button', name='套用實驗設定').click()
            page.goto(evil_same + '/playground')
            assert not page.locator('details').get_attribute('open')
            page.locator('summary').click()
            if domain == 'localhost':
                page.screenshot(path='test-results/playground.png', full_page=True)
            with page.expect_response(lambda r: r.url.split('?')[0] == bank_url + '/transfer') as pending:
                page.get_by_role('button', name='領取活動獎勵', exact=True).click()
            assert pending.value.status == 403
            page.goto(bank_url + '/bank')
            assert page.evaluate("fetch('/api/account').then(r => r.json())")['account']['balance'] == expected_balance - 17300
            if policy == 'Lax':
                page.screenshot(path='test-results/dashboard.png', full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                page.screenshot(path='test-results/mobile.png', full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            Path('test-results').mkdir(exist_ok=True)
            Path(f'test-results/browser-{policy}{"-localhost" if domain == "localhost" else ""}.json').write_text(json.dumps(observations, indent=2), encoding='utf-8')
            browser.close()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
