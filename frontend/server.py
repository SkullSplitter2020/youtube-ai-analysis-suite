#!/usr/bin/env python3
"""
Einfacher HTTP-Server ohne Cache für das Frontend.
"""
import http.server
import os

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):

    def end_headers(self):
        # Cache komplett deaktivieren
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        # Schöneres Logging
        print(f"{self.address_string()} - {args[0]} {args[1]}")


if __name__ == "__main__":
    os.chdir("/app")
    server = http.server.HTTPServer(("0.0.0.0", 80), NoCacheHandler)
    print("Frontend läuft auf Port 80")
    server.serve_forever()