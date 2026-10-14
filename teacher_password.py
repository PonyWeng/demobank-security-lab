import json, os, secrets, sqlite3
from pathlib import Path
from dotenv import dotenv_values
from werkzeug.security import generate_password_hash

ROOT=Path(__file__).resolve().parent

def bank_database():
    path=Path(dotenv_values(ROOT/'.env').get('DATABASE') or 'instance/demobank.sqlite')
    return path if path.is_absolute() else ROOT/path

def sync_password(bank_path, attacks_path, password):
    """Synchronize only the teacher identity; labs otherwise keep isolated account stores."""
    bank_path=Path(bank_path).resolve();attacks_path=Path(attacks_path).resolve()
    if not bank_path.exists() or not attacks_path.exists():
        raise ValueError('請先執行完整 setup.sh，建立銀行與 Attacks 資料庫。')
    hashed=generate_password_hash(password)
    bank_generation=secrets.token_hex(16);attacks_generation=secrets.token_hex(16)
    connection=sqlite3.connect(bank_path,timeout=10)
    try:
        connection.execute('ATTACH DATABASE ? AS attacks',(str(attacks_path),))
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            for table in ('main.users','attacks.users'):
                row=connection.execute(f'SELECT is_admin FROM {table} WHERE username=?',('pony',)).fetchone()
                if not row or not row[0]:raise ValueError('兩個資料庫都必須存在 pony 管理員。')
                connection.execute(f'UPDATE {table} SET password_hash=? WHERE username=?',(hashed,'pony'))
            connection.execute("UPDATE metadata SET value=? WHERE key='generation'",(bank_generation,))
            connection.execute("UPDATE attacks.settings SET value=? WHERE key='generation'",(attacks_generation,))
    finally:connection.close()
    bank_json=bank_path.parent/'setup-credentials.json'
    attacks_json=attacks_path.parent/'setup-credentials.json'
    for path,is_bank in [(bank_json,True),(attacks_json,False)]:
        data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if is_bank:
            entry=data.setdefault('accounts',{}).setdefault('pony',{})
            entry.update(password=password,role='admin')
        else:data['pony']=password
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(data,indent=2),encoding='utf-8');temp.chmod(0o600);os.replace(temp,path)
    return bank_generation,attacks_generation
