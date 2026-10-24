"""Serve the prototype on the local network, to try it on a phone.

    backend/.venv/Scripts/python prototype/pyodide/serve.py

Then on a phone on the same Wi-Fi open http://<this computer's IP>:8765/
(Windows may ask to allow Python through the firewall).
"""

import functools
import http.server
import socket
from pathlib import Path

from measure import PORT, Handler

HERE = Path(__file__).resolve().parent

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.connect(("192.0.2.1", 80))  # no packet is sent; picks the LAN interface
    ip = s.getsockname()[0]
print(f"open http://{ip}:{PORT}/ on the phone (Ctrl+C to stop)", flush=True)
http.server.ThreadingHTTPServer(("0.0.0.0", PORT), functools.partial(Handler, directory=str(HERE))).serve_forever()
