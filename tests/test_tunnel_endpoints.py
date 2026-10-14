import json,sqlite3
import pytest
from scripts.tunnel_endpoints import read_urls,apply_urls,PORTS

def databases(root):
    for name,table in [('instance/bank.sqlite','metadata'),('attacks/instance/lab.sqlite','settings')]:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(path) as c:c.execute(f'CREATE TABLE {table}(key TEXT PRIMARY KEY,value TEXT)')
    (root/'.env').write_text('DATABASE=instance/bank.sqlite\n')
    (root/'attacks/.env').write_text('DATABASE=instance/lab.sqlite\n')

def test_tunnel_log_auto_apply(tmp_path):
    databases(tmp_path)
    logs=tmp_path/'logs';logs.mkdir()
    expected={p:f'https://demo-{p}.trycloudflare.com' for p in PORTS}
    for p,url in expected.items():(logs/f'tunnel-{p}.log').write_text('INF | '+url+' |\n')
    apply_urls(tmp_path,read_urls(logs))
    with sqlite3.connect(tmp_path/'instance/bank.sqlite') as c:
        bank=json.loads(c.execute("SELECT value FROM metadata WHERE key='public_endpoints'").fetchone()[0])
    assert bank=={'bank':expected[5000],'playground':expected[5001]+'/playground','cross_site':True}
    with sqlite3.connect(tmp_path/'attacks/instance/lab.sqlite') as c:
        attack=json.loads(c.execute("SELECT value FROM settings WHERE key='urls'").fetchone()[0])
    assert attack=={'sql':expected[5100],'xss':expected[5101],'collector':expected[5102]}
    with pytest.raises(ValueError):apply_urls(tmp_path,{5000:expected[5000]})
    with pytest.raises(ValueError):apply_urls(tmp_path,{**expected,5102:'https://invalid.example/path'})
    with sqlite3.connect(tmp_path/'instance/bank.sqlite') as c:
        assert json.loads(c.execute('SELECT value FROM metadata').fetchone()[0])==bank

def test_second_database_failure_rolls_back(tmp_path):
    databases(tmp_path)
    with sqlite3.connect(tmp_path/'attacks/instance/lab.sqlite') as c:c.execute('DROP TABLE settings')
    with pytest.raises(sqlite3.DatabaseError):apply_urls(tmp_path,{p:f'https://demo-{p}.trycloudflare.com' for p in PORTS})
    with sqlite3.connect(tmp_path/'instance/bank.sqlite') as c:assert c.execute('SELECT count(*) FROM metadata').fetchone()[0]==0
