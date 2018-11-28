#!/usr/bin/env python3
import argparse
from glob import glob
from os.path import expanduser

from http.server import BaseHTTPRequestHandler, HTTPServer

from ics_merger import merge_files

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        files = glob(expanduser(args.directory) + "/**/*.ics")
        data = merge_files(args.calendar_name, args.calendar_description, files)

        self.send_response(200)
        self.send_header("Content-type", "text/calendar")
        self.end_headers()

        self.wfile.write(data.encode("utf-8"))
        return

def run(args):
    server_address = ("127.0.0.1", args.port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"running server: http://127.0.0.1:{args.port}/")
    httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--calendar-name", "-n", default="Output", help="the calendar name")
    parser.add_argument("--calendar-description", "-d", default="Description", help="the calendar description")
    parser.add_argument("--port", "-p", default=8991, type=int, help="port to listen on")
    parser.add_argument("directory", help="the directory containing .ics files")

    args = parser.parse_args()
    run(args)
