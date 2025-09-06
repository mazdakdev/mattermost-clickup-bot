"""
Simple health check server for the Mattermost ClickUp bot.
This allows Docker health checks and monitoring.
"""

import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "mattermost-clickup-bot"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

def start_health_server():
    """Start the health check server in a separate thread."""
    port = int(os.environ.get('WEBHOOK_HOST_PORT', 5001))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    
    print(f"Health check server starting on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

if __name__ == '__main__':
    start_health_server()
