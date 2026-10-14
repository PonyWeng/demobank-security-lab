"""Linux process manager: only stop children whose PID and start time match our records."""
import json, os, re, shutil, signal, socket, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'instance/services'
PORTS=[5000,5001,5100,5101,5102]

def identity(pid):
    try:
        raw=Path(f'/proc/{pid}/stat').read_text()
        tail=raw[raw.rfind(')')+2:].split()
        if tail[0]=='Z':return None
        return tail[19]
    except (OSError,IndexError):return None

def alive(record):
    return identity(record['pid'])==record['start'] and record['start'] is not None

def launch(command,log):
    with log.open('wb') as out:
        process=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
    time.sleep(.2)
    record={'pid':process.pid,'start':identity(process.pid),'command':command}
    if not alive(record):raise RuntimeError(f'Start failed: see {log}')
    return record

def stop_records(records):
    for record in records:
        if alive(record):os.kill(record['pid'],signal.SIGTERM)
    until=time.monotonic()+8
    while time.monotonic()<until and any(alive(r) for r in records):time.sleep(.1)
    if any(alive(r) for r in records):raise RuntimeError('A managed process did not stop; inspect its log. No unrelated processes were killed.')

def open_port(port):
    with socket.socket() as s:
        s.settimeout(.2)
        return s.connect_ex(('127.0.0.1',port))==0

def main():
    if sys.platform!='linux':raise SystemExit('These background service scripts require Linux. Windows: python run_all.py')
    import fcntl
    os.umask(0o077)
    STATE.mkdir(parents=True,exist_ok=True)
    action=sys.argv[1] if len(sys.argv)>1 else 'status'
    tunnel=action.startswith('tunnels-')
    file=STATE/('tunnels.json' if tunnel else 'services.json')
    with (STATE/'manager.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        records=json.loads(file.read_text()) if file.exists() else []
        if action in ('stop','tunnels-stop'):
            stop_records(records)
            file.write_text('[]')
            print('Stopped only recorded '+('lab tunnels' if tunnel else 'lab services'))
        elif action=='status':
            print('Services: '+('running' if records and all(alive(r) for r in records) else 'stopped'))
        elif action=='tunnels-urls':print_urls()
        elif action in ('start','tunnels-start'):
            if any(alive(r) for r in records):
                print('Already running; stop before restarting.')
                return
            created=[]
            try:
                if not tunnel:
                    occupied=[p for p in PORTS if open_port(p)]
                    if occupied:raise RuntimeError(f'Ports already occupied: {occupied}. Existing services were not stopped.')
                    created.append(launch([sys.executable,str(ROOT/'run_all.py')],STATE/'services.log'))
                    deadline=time.monotonic()+10
                    while time.monotonic()<deadline and alive(created[0]) and not all(open_port(p) for p in PORTS):time.sleep(.2)
                    if not all(open_port(p) for p in PORTS):raise RuntimeError('Service readiness failed; see instance/services/services.log')
                else:
                    binary=shutil.which('cloudflared')
                    if not binary:raise RuntimeError('Install official cloudflared first.')
                    if not all(open_port(p) for p in PORTS):raise RuntimeError('Start all services before starting tunnels.')
                    for port in PORTS:
                        created.append(launch([binary,'tunnel','--url',f'http://127.0.0.1:{port}'],STATE/f'tunnel-{port}.log'))
                file.write_text(json.dumps(created,indent=2))
            except Exception:
                stop_records(created)
                raise
            print('Started '+('five tunnels; use bash cloudflared.sh urls after URLs appear' if tunnel else 'all five services; hub: http://localhost:5000/labs'))
        else:raise RuntimeError('Unknown action')

def print_urls():
    for port in PORTS:
        path=STATE/f'tunnel-{port}.log'
        found=re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com',path.read_text(errors='replace')) if path.exists() else []
        print(f'{port}: {found[0] if found else "pending; inspect tunnel log"}')

if __name__=='__main__':
    try:main()
    except Exception as error:raise SystemExit(str(error))
