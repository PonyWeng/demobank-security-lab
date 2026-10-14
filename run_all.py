"""Start isolated CSRF, SQL and XSS services with one foreground process."""
import signal, threading
from waitress import create_server
from bank import create_app
from bank.endpoints import endpoints
from attacks.lab import create_app as create_attack_app
import attacker

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--port-offset',type=int,default=0,help='Offset all ports for isolated testing')
    offset=parser.parse_args().port_offset
    servers=[]
    app=create_app()
    def target():
        with app.app_context():return endpoints()['bank']
    attacker.app.config['ENDPOINT_PROVIDER']=target
    try:
        apps=[('bank',5000,app),('playground',5001,attacker.app)]
        apps.extend((name,port,create_attack_app(name)) for name,port in [('sql',5100),('xss',5101),('collector',5102)])
        for name,port,application in apps:
            port+=offset
            server=create_server(application,host='127.0.0.1',port=port,threads=6)
            servers.append(server)
            print(f'{name}: 127.0.0.1:{port}',flush=True)
        def stop(*_):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,stop)
        for server in servers[1:]:threading.Thread(target=server.run,daemon=True).start()
        servers[0].run()
    except KeyboardInterrupt:pass
    finally:
        for server in servers:server.close()

if __name__=='__main__':main()
