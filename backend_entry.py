"""Bundled Python sidecar entry point; no external Python needed in releases."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--ready-file', type=Path, required=True)
    args = parser.parse_args()
    import uvicorn
    from app import app

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind before reporting readiness; an existing process must never be mistaken for ours.
    try:
        sock.bind(('127.0.0.1', args.port))
    except OSError:
        sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, access_log=False, log_level='warning', ws='none', loop='asyncio', http='h11'))

    def report_ready():
        while not server.started and not server.should_exit:
            time.sleep(.05)
        if server.started:
            args.ready_file.write_text(json.dumps({'port':port,'pid':os.getpid()}), encoding='utf-8')

    def watch_parent():
        # Electron owns stdin. EOF means it exited, including crashes; stop the service.
        sys.stdin.buffer.read()
        server.should_exit = True

    threading.Thread(target=report_ready, daemon=True).start()
    threading.Thread(target=watch_parent, daemon=True).start()
    try:
        server.run(sockets=[sock])
    finally:
        sock.close()
        args.ready_file.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
