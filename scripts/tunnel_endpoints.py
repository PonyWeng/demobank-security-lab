"""Apply a complete set of managed Quick Tunnel URLs to both lab databases."""
import json, re, sqlite3
from pathlib import Path
from dotenv import dotenv_values

PORTS=(5000,5001,5100,5101,5102)

def read_urls(state):
    result={}
    for port in PORTS:
        path=Path(state)/f'tunnel-{port}.log'
        if path.exists():
            found=re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com',path.read_text(errors='replace'))
            if found:result[port]=found[0]
    return result

def apply_urls(root,urls):
    root=Path(root)
    if set(urls)!=set(PORTS) or len(set(urls.values()))!=5:
        raise ValueError('Need five distinct Tunnel URLs; existing endpoint settings preserved.')
    for value in urls.values():
        if not re.fullmatch(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com',value):
            raise ValueError('Invalid Quick Tunnel URL; existing settings preserved.')
    def path(env_path,default,base):
        value=Path(dotenv_values(env_path).get('DATABASE') or default)
        return value if value.is_absolute() else base/value
    bank=path(root/'.env','instance/demobank.sqlite',root)
    attacks=path(root/'attacks/.env','instance/attacks.sqlite',root/'attacks')
    if not bank.exists() or not attacks.exists():raise ValueError('Run setup.sh first; both databases must exist.')
    connection=sqlite3.connect(bank,timeout=10)
    try:
        connection.execute('ATTACH DATABASE ? AS attacks',(str(attacks),))
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute("INSERT INTO metadata(key,value) VALUES ('public_endpoints',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps({'bank':urls[5000],'playground':urls[5001]+'/playground','cross_site':True}),))
            connection.execute("INSERT INTO attacks.settings(key,value) VALUES ('urls',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps({'sql':urls[5100],'xss':urls[5101],'collector':urls[5102]}),))
    finally:connection.close()
