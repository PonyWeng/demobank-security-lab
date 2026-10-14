import argparse
import threading
from waitress import create_server
from bank import create_app

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--playground-port', type=int, default=5001)
    parser.add_argument('--bank-only', action='store_true', help='Only start the bank service')
    args = parser.parse_args()
    app = create_app()
    server = create_server(app, host=args.host, port=args.port, threads=8)
    playground = None
    if not args.bank_only:
        from attacker import app as attacker_app
        from bank.endpoints import endpoints
        def endpoint_provider():
            with app.app_context():
                return endpoints()['bank']
        attacker_app.config['ENDPOINT_PROVIDER'] = endpoint_provider
        try:
            playground = create_server(attacker_app, host=args.host, port=args.playground_port, threads=4)
        except OSError:
            server.close()
            raise SystemExit('Playground port is occupied. Stop attacker.py or use --playground-port PORT.')
        threading.Thread(target=playground.run, daemon=True).start()
    print(f'DemoBank is running: {app.config["BANK_ORIGIN"]}', flush=True)
    print(f'Listening on {args.host}:{args.port}. Keep this terminal open; press Ctrl+C to stop.', flush=True)
    if playground:
        print(f'Payload playground: {app.config["PLAYGROUND_URL"]}', flush=True)
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        if playground:
            playground.close()
