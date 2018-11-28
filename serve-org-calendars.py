#!/usr/bin/env python3
import argparse
from configparser import ConfigParser, NoOptionError, NoSectionError
from glob import glob
from os.path import expanduser

from http.server import BaseHTTPRequestHandler, HTTPServer

from ics_merger import merge_files

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        for name, calendar in RequestHandler.calendars.items():
            if self.path == "/" + name + "/":
                self.send_calendar(calendar)
                return

    def send_calendar(self, calendar):
        files = glob(expanduser(calendar["directory"]) + "/**/*.ics")
        data = merge_files(calendar["name"], calendar["description"], files)

        self.send_response(200)
        self.send_header("Content-type", "text/calendar")
        self.end_headers()

        self.wfile.write(data.encode("utf-8"))

def get_port(config):
    try:
        return config.getint("general", "port")
    except (NoSectionError, NoOptionError):
        return 8991

def load_calendars(config):
    calendars = {}
    for section in config.sections():
        if section.startswith("calendar "):
            name = section.split(" ", 1)[1]
            calendars[name] = config[section]
            assert calendars[name]["directory"]
            assert calendars[name]["name"]
            assert calendars[name]["description"]

    return calendars

def run(args):
    config = ConfigParser()
    config.read(expanduser(args.config))
    RequestHandler.calendars = load_calendars(config)

    port = get_port(config)
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"running server: http://127.0.0.1:{port}/")
    for name, calendar in RequestHandler.calendars.items():
        print(f"    serving http://127.0.0.1:{port}/{name}/")

    httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", default="~/.serve-org-calendars.conf", help="the config file to load")

    args = parser.parse_args()
    run(args)
