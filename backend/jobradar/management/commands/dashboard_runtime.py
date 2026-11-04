"""A single owned local WSGI server and authenticated loopback control channel."""
import hmac
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

from django.core.management.base import BaseCommand, CommandError
from django.core.wsgi import get_wsgi_application
from django.conf import settings

from jobradar.services import application_prep
from jobradar.services.processing_control import Store, recover_pending, event


class ThreadedWSGI(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class Command(BaseCommand):
    help = 'Serve the existing local app with cooperative dashboard lifecycle control.'

    def add_arguments(self, parser):
        parser.add_argument('--port', type=int, default=8000)
        parser.add_argument('--control-port', type=int, default=8096)

    def handle(self, *args, **options):
        database = os.environ.get('DACHAPPLY_CONTROL_DB')
        token = os.environ.get('DACHAPPLY_CONTROL_TOKEN', '')
        if not database or len(token) < 32:
            raise CommandError('The dashboard must supply a private control database and token.')
        control = Store(database)
        handler = RotatingFileHandler(Path(database).parent / 'execution.log', maxBytes=256_000, backupCount=1, encoding='utf-8')
        handler.setFormatter(logging.Formatter('DASHBOARD_EVENT %(message)s'))
        events = logging.getLogger('dashboard.events')
        events.setLevel(logging.INFO)
        events.propagate = False
        events.addHandler(handler)

        class SafeErrors(logging.Handler):
            def emit(self, record):
                event('execution_error')  # deliberately exclude message/args/traceback
        errors = SafeErrors(logging.ERROR)
        logging.getLogger().addHandler(errors)
        stopping = threading.Event()
        commands = threading.Lock()
        requests = [0]
        request_lock = threading.Lock()
        application = get_wsgi_application()

        def draining_app(environ, start_response):
            with request_lock:
                if stopping.is_set() and environ['REQUEST_METHOD'] not in ('GET', 'HEAD', 'OPTIONS'):
                    start_response('503 Service Unavailable', [('Content-Type', 'text/plain')])
                    return [b'Dachapply is draining for shutdown.']
                requests[0] += 1
            def response():
                result = None
                try:
                    result = application(environ, start_response)
                    yield from result
                finally:
                    if result is not None and hasattr(result, 'close'):
                        result.close()
                    with request_lock:
                        requests[0] -= 1
            return response()

        # Socket binding is the cross-process singleton: a second server cannot recover/alter work.
        server = make_server('0.0.0.0' if settings.LAN_ACCESS else '127.0.0.1', options['port'], draining_app, server_class=ThreadedWSGI)

        class Handler(BaseHTTPRequestHandler):
            def respond(self, code, body):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def authorized(self):
                return (self.client_address[0] == '127.0.0.1'
                        and self.headers.get('Host') == f'127.0.0.1:{options["control_port"]}'
                        and not self.headers.get('Origin')
                        and hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token))

            def do_GET(self):
                if not self.authorized():
                    return self.respond(403, {'error': 'Forbidden'})
                if self.path != '/status':
                    return self.respond(404, {'error': 'Unknown action'})
                with application_prep._lock:
                    state = control.status()
                    state['remaining_jobs'] += len(application_prep._queue)
                state.update(pid=os.getpid(), instance=os.environ['DACHAPPLY_INSTANCE'], running=True)
                self.respond(200, state)

            def do_POST(self):
                if not self.authorized():
                    return self.respond(403, {'error': 'Forbidden'})
                if self.path not in ('/pause', '/resume', '/stop'):
                    return self.respond(404, {'error': 'Unknown action'})
                with commands:
                    if stopping.is_set() and self.path != '/stop':
                        return self.respond(409, {'error': 'Shutdown is draining; wait for Start.'})
                    control.mode({'/pause': 'paused', '/resume': 'running', '/stop': 'stopping'}[self.path])
                    if self.path == '/resume':
                        with application_prep._lock:
                            application_prep._pump()
                    if self.path == '/stop':
                        stopping.set()
                event(self.path[1:])
                self.respond(202, {'ok': True})

            def log_message(self, *args):
                pass

        channel = ThreadingHTTPServer(('127.0.0.1', options['control_port']), Handler)
        channel_started = False
        try:
            recover_pending()
            # Resume documents before readiness. A saved pause remains paused after restart.
            application_prep.resume_queue()
            from jobradar.services.mailbox_loop import _loop
            if os.environ.get('DACHAPPLY_LOCAL_MAILBOX_LOOP', '1') != '0':
                threading.Thread(target=_loop, daemon=True).start()
            threading.Thread(target=channel.serve_forever, daemon=True).start()
            channel_started = True

            def drain():
                stopping.wait()
                while control.status()['running_jobs'] or requests[0]:
                    time.sleep(.1)
                server.shutdown()
            threading.Thread(target=drain, daemon=True).start()
            event('ready')
            server.serve_forever()
        finally:
            if channel_started:
                channel.shutdown()
            channel.server_close()
            server.server_close()
            logging.getLogger().removeHandler(errors)
            events.removeHandler(handler)
            handler.close()
