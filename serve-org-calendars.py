#!/usr/bin/env python3
import argparse
import dateparser
import pytz
import re
import warnings
from datetime import datetime, timedelta
from configparser import ConfigParser, NoOptionError, NoSectionError
from glob import glob
from http.server import BaseHTTPRequestHandler, HTTPServer
from icalendar import Calendar, Event
from os.path import expanduser
from PyOrgMode import PyOrgMode
from time import mktime
from ics_merger import merge_files

warnings.simplefilter(action='ignore', category=FutureWarning)

ORG_CALENDARS = ("deadline", "scheduled", "closed", "clocks")
CLOCK_PATTERN = re.compile(r'CLOCK: \[(?P<start>.*)\]--\[(?P<end>.*)\].*')
TIMEZONE = "Europe/Berlin"

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

def clean_heading(heading):
    return re.sub(r'\[\[.*?\]\[(.*?)\]\]', r'\1', heading)

def read_time_from_element(element, which, results):
    if not hasattr(element, which) or \
       not hasattr(getattr(element, which), "value"):
        return

    value = getattr(element, which).value
    if isinstance(value, str):
        # whichasn't parsed by PyOrgMode, so probably something like
        # <2018-12-09 Sun 06:30 ++2w/3w -2d>
        # ignore these
        return

    dt = datetime.fromtimestamp(
        mktime(value),
        pytz.timezone("Europe/Berlin"))

    return dt

def collect_times_from_org_files(files):
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
                path.append(clean_heading(element.heading))
                continue

            elif isinstance(element, PyOrgMode.OrgDrawer.Element):
                for line in element.content:
                    if not isinstance(line, str):
                        continue

                    mo = CLOCK_PATTERN.match(line)
                    if not mo:
                        continue

                    settings = {
                        'TIMEZONE': TIMEZONE,
                        'RETURN_AS_TIMEZONE_AWARE': True,
                    }
                    start = dateparser.parse(mo.group("start"), settings=settings)
                    end = dateparser.parse(mo.group("end"), settings=settings)
                    results["clocks"].append((list(path), start, end))

            elif isinstance(element, PyOrgMode.OrgSchedule.Element):
                for w in ("deadline", "scheduled", "closed"):
                    dt = read_time_from_element(element, w, results)
                    if dt:
                        results[w].append((list(path), dt, None))

    return results

def create_calendar(files, which):
    results = collect_times_from_org_files(files)
    cal = Calendar()
    cal.add('prodid', '-//serve-org-calendar//v0.1//')
    cal.add('version', '2.0')
    cal.add('calscale', "GREGORIAN")
    cal.add("X-WR-CALNAME;VALUE=TEXT", which)
    cal.add("X-WR-CALDESC;VALUE=TEXT", which + " imported from org-mode")
    min_time = datetime.now(pytz.timezone(TIMEZONE)) - timedelta(days=30)
    max_time = datetime.now(pytz.timezone(TIMEZONE)) + timedelta(days=30)
    for path, dt, dtend in results[which]:
        if dt < min_time or dt > max_time:
            continue

        event = Event()
        headings = [x.strip() for x in path if x.strip()]
        if not headings:
            headings = ["dummy"]
        event.add('summary', headings[-1])
        event.add('description', '\n'.join("*" * i + " " + x for i, x in enumerate(headings)))
        event.add('dtstart', dt)
        if not dtend:
            dtend = dt + timedelta(seconds=15 * 60)
        event.add('dtend', dtend)
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
