"""Run server in background and wait for requests."""
import os
import socket
import subprocess
import sys
import time


def get_free_port(start_port: int = 8000, max_port: int = 8100) -> int:
    port = start_port
    while port <= max_port:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('127.0.0.1', port))
                return port
            except OSError:
                port += 1
    raise RuntimeError(f'No free port found between {start_port} and {max_port}.')


workdir = os.path.dirname(os.path.abspath(__file__))
port = int(os.environ.get('PORT', str(get_free_port())))
log_path = os.path.join(workdir, 'server_debug.log')

with open(log_path, 'w', encoding='utf-8') as log:
    proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', str(port)],
        cwd=workdir,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    print(f'SERVER_PID={proc.pid}')
    print(f'PORT={port}')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        proc.kill()
