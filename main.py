# from bridge import Bridge # Is used for communication between the MPU and the MCU
# TODO: Use uvicorn later for faster webserver

from http.server import HTTPServer, BaseHTTPRequestHandler


class App(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Hello")


server = HTTPServer(("0.0.0.0", 8000), App)
server.serve_forever()
