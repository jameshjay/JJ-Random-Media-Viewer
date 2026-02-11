#!/usr/bin/env python3

import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8000
DB_PATH = Path("favorites_db.json")
MEDIA_ROOT = Path("/Users/JJ2/Library/CloudStorage/GoogleDrive-jameshjay22@gmail.com/My Drive/JJ_Random")


def load_db():
    if not DB_PATH.exists():
        return {"favorites": []}
    try:
        data = json.loads(DB_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"favorites": []}
    if not isinstance(data, dict):
        return {"favorites": []}

    favorites = data.get("favorites", [])
    if not isinstance(favorites, list):
        favorites = []

    cleaned = []
    for item in favorites:
        if isinstance(item, str) and item.strip():
            cleaned.append(item.strip().lower())

    return {"favorites": sorted(set(cleaned))}


def save_db(db):
    payload = {"favorites": sorted(set(db.get("favorites", [])))}
    DB_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def resolve_media_relative_path(relative_path: str):
    if not MEDIA_ROOT.exists() or not MEDIA_ROOT.is_dir():
        return None, "MEDIA_ROOT is not configured to a valid folder."

    candidate = (MEDIA_ROOT / Path(relative_path)).resolve()
    root_resolved = MEDIA_ROOT.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None, "Invalid path."

    if not candidate.exists() or not candidate.is_file():
        return None, "File not found under MEDIA_ROOT."

    return candidate, None


def reveal_in_finder(path: Path):
    try:
        subprocess.run(["open", "-R", str(path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, None
    except subprocess.CalledProcessError as exc:
        error_text = (exc.stderr or exc.stdout or "").strip() or "Unknown error."
        return False, f"Could not reveal in Finder: {error_text}"


class AppHandler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, file_path: Path, content_type: str):
        try:
            data = file_path.read_bytes()
        except OSError:
            self.send_error(404, "File not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self.serve_file(Path("index.html"), "text/html; charset=utf-8")
            return
        if path == "/api/favorites":
            db = load_db()
            self.send_json({"ok": True, "favorites": db["favorites"]})
            return
        if path == "/api/health":
            self.send_json(
                {
                    "ok": True,
                    "mediaRoot": str(MEDIA_ROOT),
                    "mediaRootConfigured": MEDIA_ROOT.exists() and MEDIA_ROOT.is_dir(),
                }
            )
            return
        self.send_error(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {"/api/favorites", "/api/reveal"}:
            self.send_error(404, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"ok": False, "error": "Invalid Content-Length."}, 400)
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json({"ok": False, "error": "Invalid JSON body."}, 400)
            return

        if path == "/api/reveal":
            relative_path = payload.get("relativePath")
            if not isinstance(relative_path, str) or not relative_path.strip():
                self.send_json({"ok": False, "error": "relativePath is required."}, 400)
                return

            file_path, resolve_error = resolve_media_relative_path(relative_path.strip())
            if resolve_error:
                self.send_json({"ok": False, "error": resolve_error}, 400)
                return

            revealed, reveal_error = reveal_in_finder(file_path)
            if not revealed:
                self.send_json({"ok": False, "error": reveal_error}, 500)
                return

            self.send_json({"ok": True, "revealed": relative_path})
            return

        favorites = payload.get("favorites")
        if not isinstance(favorites, list):
            self.send_json({"ok": False, "error": "favorites array is required."}, 400)
            return

        cleaned = []
        for item in favorites:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip().lower())

        try:
            save_db({"favorites": cleaned})
        except OSError as exc:
            self.send_json({"ok": False, "error": f"Could not save DB: {exc}"}, 500)
            return

        self.send_json({"ok": True, "favorites": sorted(set(cleaned))})

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    with ThreadingHTTPServer((HOST, PORT), AppHandler) as httpd:
        print(f"Serving app on http://{HOST}:{PORT}")
        print(f"Favorites DB: {DB_PATH.resolve()}")
        httpd.serve_forever()
