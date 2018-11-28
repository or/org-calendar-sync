#!/usr/bin/env python3
import argparse
import pytz
from datetime import datetime, timedelta
from configparser import ConfigParser, NoOptionError, NoSectionError
from glob import glob
from http.server import BaseHTTPRequestHandler, HTTPServer
from icalendar import Calendar, Event
from os.path import expanduser
from PyOrgMode import PyOrgMode
from time import mktime

from ics_merger import merge_files

ORG_CALENDARS = ("deadline", "scheduled", "closed", "clocks")

def get_org_files():
    return glob(expanduser(expanduser("~/org/**/*.org")), recursive=True) + \
        glob(expanduser(expanduser("~/org/**/*.org_archive")), recursive=True)

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        for name, calendar in RequestHandler.calendars.items():
            if self.path == "/" + name + "/":
                self.send_calendar(calendar)
                return

        for w in ORG_CALENDARS:
            if self.path == "/org/" + w + "/":
                files = get_org_files()
                data = create_calendar(files, w)
                self.send_calendar_file(data)

    def send_calendar(self, calendar):
        files = glob(expanduser(calendar["directory"]) + "/**/*.ics")
        data = merge_files(calendar["name"], calendar["description"], files)
        self.send_calendar_file(data)

    def send_calendar_file(self, data):
        self.send_response(200)
        self.send_header("Content-type", "text/calendar")
        self.end_headers()

        if isinstance(data, str):
            data = data.encode("utf-8")

        self.wfile.write(data)

def create_calendar(files, which):
    results = {}
    for w in ORG_CALENDARS:
        results[w] = []

    for f in files:
        org = PyOrgMode.OrgDataStructure()
        org.load_from_file(expanduser(f))
        todo = [org.root]
        path = []
        while todo:
            element = todo.pop(0)
            if element is None:
                if path:
                    path.pop(-1)

                continue

            if isinstance(element, PyOrgMode.OrgNode.Element):
                todo = element.content + [None] + todo
                path.append(element.heading)
                continue

            if isinstance(element, PyOrgMode.OrgSchedule.Element):
                for w in ("deadline", "scheduled", "closed"):
                    if not hasattr(element, w) or \
                       not hasattr(getattr(element, w), "value"):
                        continue

                    dt = datetime.fromtimestamp(
                        mktime(getattr(element, w).value),
                        pytz.timezone("Europe/Berlin"))

                    results[w].append((list(path), dt))

    cal = Calendar()
    cal.add('prodid', '-//serve-org-calendar//v0.1//')
    cal.add('version', '2.0')
    cal.add('calscale', "GREGORIAN")
    cal.add("X-WR-CALNAME;VALUE=TEXT", which)
    cal.add("X-WR-CALDESC;VALUE=TEXT", which + " imported from org-mode")
    for path, dt in results[which]:
        event = Event()
        headings = [x.strip() for x in path if x.strip()]
        if not headings:
            headings = ["dummy"]
        event.add('summary', headings[-1])
        event.add('description', '\n'.join("*" * i + " " + x for i, x in enumerate(headings)))
        event.add('dtstart', dt)
        event.add('dtend', dt + timedelta(seconds=15 * 60))
        event.add('dtstamp', dt)
        cal.add_component(event)

    return cal.to_ical()

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
            assert name != "org"
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
        for w in ORG_CALENDARS:
            print(f"    serving http://127.0.0.1:{port}/org/{w}/")

    httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", default="~/.serve-org-calendars.conf", help="the config file to load")

    args = parser.parse_args()
    run(args)
