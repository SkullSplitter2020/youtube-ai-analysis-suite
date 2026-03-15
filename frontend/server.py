#!/usr/bin/env python3
"""
Einfacher HTTP-Server für das Frontend
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        SimpleHTTPRequestHandler.end_headers(self)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    server = HTTPServer(('0.0.0.0', port), CORSRequestHandler)
    print(f"Frontend Server läuft auf http://0.0.0.0:{port}")
    print(f"API wird erwartet unter: http://192.168.178.40:8000")
    sys.stdout.flush()  # Wichtig für Docker-Logs
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
        server.shutdown()