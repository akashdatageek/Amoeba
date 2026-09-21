#!/usr/bin/env python3
"""Serve the architecture page locally and collect per-box change requests.

    python serve_edits.py amoeba_phase1.html            # http://localhost:8765
Clicking a box (or the pencil on a top-level box) in the page POSTs
{view, box, request, ts, page} to /edit; each request is appended to edits.jsonl
next to the HTML file. Claude Code reads edits.jsonl and applies the changes.
"""
import json, sys, os, http.server, socketserver, datetime

PAGE = sys.argv[1] if len(sys.argv) > 1 else "amoeba_phase1.html"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
ROOT = os.path.dirname(os.path.abspath(PAGE)) or "."
LOG = os.path.join(ROOT, "edits.jsonl")

class H(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, '.html': 'text/html; charset=utf-8'}
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def do_GET(self):
        if self.path in ("/", ""): self.path = "/" + os.path.basename(PAGE)
        return super().do_GET()
    def do_POST(self):
        if self.path != "/edit": self.send_error(404); return
        n = int(self.headers.get("Content-Length", 0)); rec = json.loads(self.rfile.read(n) or b"{}")
        rec.setdefault("ts", datetime.datetime.now().isoformat()); rec["status"] = "pending"
        with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
        print(f"[edit] {rec.get('view')}/{rec.get('box')}: {rec.get('request')}")
        self.send_response(204); self.end_headers()
    def log_message(self, *a): pass

with socketserver.TCPServer(("127.0.0.1", PORT), H) as s:
    print(f"serving {PAGE} at http://localhost:{PORT}  (edits -> {LOG})"); s.serve_forever()
