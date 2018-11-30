#!/usr/bin/env python3
import argparse
import re
import threading
import time
import warnings
from configparser import ConfigParser
from datetime import datetime, timedelta
from glob import glob
from http.server import BaseHTTPRequestHandler, HTTPServer
from icalendar import Calendar, Event
from os.path import expanduser
from PyOrgMode import PyOrgMode
from time import mktime
from tzlocal import get_localzone

from orgmode_sync.ics_merger import merge_files
from orgmode_sync.orgmode_sync import get_events, import_to_org

warnings.simplefilter(action='ignore', category=FutureWarning)

ORG_CALENDARS = ("active-deadline", "deadline", "active-scheduled", "scheduled", "closed", "clocks")
CLOCK_PATTERN = re.compile(r'CLOCK: \[(?P<start>.*)\]--\[(?P<end>.*)\].*')
TIMEZONE = get_localzone()

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

def read_time_from_element(element, which):
    if not hasattr(element, which) or \
       not hasattr(getattr(element, which), "value"):
        return

    value = getattr(element, which).value
    if isinstance(value, str):
        # whichasn't parsed by PyOrgMode, so probably something like
        # <2018-12-09 Sun 06:30 ++2w/3w -2d>
        # ignore these
        return

    dt = datetime.fromtimestamp(mktime(value), TIMEZONE)

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
                copied_path = tuple(path)
                for line in element.content:
                    if not isinstance(line, str):
                        continue

                    mo = CLOCK_PATTERN.match(line)
                    if not mo:
                        continue

                    start = datetime.strptime(mo.group("start"), "%Y-%m-%d %a %H:%M").replace(tzinfo=TIMEZONE)
                    end = datetime.strptime(mo.group("end"), "%Y-%m-%d %a %H:%M").replace(tzinfo=TIMEZONE)
                    results["clocks"].append((copied_path, start, end))

            elif isinstance(element, PyOrgMode.OrgSchedule.Element):
                closed = read_time_from_element(element, "closed")
                is_closed = False
                if closed:
                    results["closed"].append((list(path), closed, None))
                    is_closed = True

                for w in ("deadline", "scheduled"):
                    dt = read_time_from_element(element, w)
                    if dt:
                        results[w].append((list(path), dt, None))
                        if not is_closed:
                            results["active-" + w].append((list(path), dt, None))

    return results

def create_calendar(files, which):
    results = collect_times_from_org_files(files)
    cal = Calendar()
    cal.add('prodid', '-//serve-org-calendar//v0.1//')
    cal.add('version', '2.0')
    cal.add('calscale', "GREGORIAN")
    cal.add("X-WR-CALNAME;VALUE=TEXT", which)
    cal.add("X-WR-CALDESC;VALUE=TEXT", which + " imported from org-mode")
    min_time = datetime.now(TIMEZONE) - timedelta(days=30)
    max_time = datetime.now(TIMEZONE) + timedelta(days=30)
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

def serve_calendars(config):
    RequestHandler.calendars = load_calendars(config)

    if config.has_option("serve", "port"):
        port = config.getint("serve", "port")
    else:
        port = 8991

    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"running server: http://127.0.0.1:{port}/")
    for name, calendar in calendars_to_serve.items():
        print(f"    serving http://127.0.0.1:{port}/{name}/")
        for w in ORG_CALENDARS:
            print(f"    serving http://127.0.0.1:{port}/org/{w}/")

    httpd.serve_forever()

def import_calendar(config):
    output_file = config.get("import", "output_file")

    if config.has_option("import", "delay"):
        delay = config.getint("import", "delay")
    else:
        delay = 300

    if config.has_option("import", "num_days"):
        num_days = config.getint("import", "num_days")
    else:
        num_days = 30

    if config.has_option("import", "include_end_time"):
        include_end_time = config.getboolean("import", "include_end_time")
    else:
        include_end_time = None

    if config.has_option("import", "include_duration"):
        include_duration = config.getboolean("import", "include_duration")
    else:
        include_duration = None

    if config.has_option("import", "include_calendars"):
        include_calendars = config.get("import", "include_calendars").split()
    else:
        include_calendars = None

    if config.has_option("import", "exclude_calendars"):
        exclude_calendars = config.get("import", "exclude_calendars").split()
    else:
        exclude_calendars = None

    while True:
        start_time = datetime.now() - timedelta(days=num_days)
        end_time = datetime.now() + timedelta(days=num_days)
        events = get_events(
            start_time,
            end_time,
            include_calendars=include_calendars,
            exclude_calendars=exclude_calendars)

        print("importing calendars to org...")
        import_to_org(
            events,
            output_file=output_file,
            include_end_time=include_end_time,
            include_duration=include_duration)

        time.sleep(delay)

def run(args):
    config = ConfigParser()
    config.read(expanduser(args.config))

    serve_calendars(config)
    serve_thread = threading.Thread(target=serve_calendars, args=(config,))
    import_thread = threading.Thread(target=import_calendar, args=(config,))
    serve_thread.start()
    import_thread.start()

    serve_thread.join()
    import_thread.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", default="~/.sync-org-calendars.conf", help="the config file to load")

    args = parser.parse_args()
    # files = ["~/test.org"]
    # data = create_calendar(files, "deadline")
    # open("test.ics", "wb").write(data)
    run(args)
