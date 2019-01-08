#!/usr/bin/env python3
import os.path
import re
from datetime import datetime, timedelta
from EventKit import EKEventStore, EKEntityMaskEvent, NSDate
from PyOrgMode import PyOrgMode
from time import mktime
from tzlocal import get_localzone

ORG_TIME_FORMAT = "%Y-%m-%d %a %H:%M"
TIMEZONE = get_localzone()
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S %z"
ORG_CALENDARS = ("active-deadline", "deadline", "active-scheduled", "scheduled", "closed", "clocks")
CLOCK_PATTERN = re.compile(r'CLOCK: \[(?P<start>.*)\]--\[(?P<end>.*)\].*')
INCOMPLETE_CLOCK_PATTERN = re.compile(r'CLOCK: \[(?P<start>.*)\]')

def get_events(start_time, end_time,
               include_calendars=None,
               exclude_calendars=None):
    store = EKEventStore.alloc()
    store.initWithAccessToEntityTypes_(EKEntityMaskEvent)

    nsdate = NSDate.date()
    start = NSDate.initWithTimeIntervalSince1970_(nsdate, start_time.timestamp())
    end = NSDate.initWithTimeIntervalSince1970_(nsdate, end_time.timestamp())

    calendars = store.allCalendars()
    if include_calendars:
        calendars = [x for x in calendars if x.title().lower() in [y.lower() for y in include_calendars]]

    if exclude_calendars:
        calendars = [x for x in calendars if x.title().lower() not in [y.lower() for y in exclude_calendars]]

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(start, end, calendars)
    events = store.eventsMatchingPredicate_(predicate)

    return events

def remove_brackets(s):
    if not s:
        return s

    return s.replace("[", "").replace("]", "")

def fix_title(s):
    if not s:
        return s

    s = remove_brackets(s)

    MAX_LENGTH = 50
    if len(s) > MAX_LENGTH:
        s = s[:MAX_LENGTH - 3] + "..."

    return s

def convert_to_tag(name):
    return name.lower().replace(" ", "-")

def create_element(events, include_end_time=False):
    event = events[0]
    element = PyOrgMode.OrgNode.Element()
    element.level = 1
    element.heading = fix_title(event["title"])
    if event.get("duration"):
        element.heading = "[" + event["duration"] + "] " + element.heading

    if event.get("part"):
        element.heading = element.heading + " [" + event["part"] + "]"

    # assure some distance of the tags
    element.heading += "            "
    element.tags = [convert_to_tag(event["event"].calendar().title())]

    drawer = PyOrgMode.OrgDrawer.Element("SCHEDULE")
    element.append_clean(drawer)

    for e in events:
        start = e["start"]
        if include_end_time:
            end = e["end"]
            if (end.hour, end.minute, end.second) == (0, 0, 0):
                end -= timedelta(seconds=1)

            drawer.append("<{start}>--<{end}>".format(
                start=start.strftime(ORG_TIME_FORMAT),
                end=end.strftime(ORG_TIME_FORMAT)))
        else:
            drawer.append("<{start}>".format(start=start.strftime(ORG_TIME_FORMAT)))

    return element

def add_events(org_data, events, include_end_time=False):
    element = create_element(events, include_end_time=include_end_time)
    if element:
        org_data.root.append_clean(element)
        org_data.root.append_clean("\n")

def get_duration_string(start, end):
    duration = end - start
    if duration.total_seconds() >= 86400 - 1:
        return "day"

    hours = duration.seconds / 3600
    if hours == 0.25:
        return "1/4h"

    elif hours == 0.5:
        return "1/2h"

    elif hours == 0.75:
        return "3/4h"

    elif hours < 1:
        mins = duration.seconds // 60
        return f"{mins}m"

    return f"{hours:.1f}h"

def transform_event(event, include_duration=False):
    new_events = []
    start = datetime.strptime(str(event.startDate()), TIMESTAMP_FORMAT).astimezone(TIMEZONE)
    end = datetime.strptime(str(event.endDate()), TIMESTAMP_FORMAT).astimezone(TIMEZONE)

    current = start
    while True:
        e = {
            "start": current,
            "title": event.title(),
            "event": event,
        }

        if current.date() == end.date():
            if (end - current).total_seconds() >= 60:
                e["end"] = end
                new_events.append(e)

            break

        e["end"] = datetime(current.year, current.month, current.day, 23, 59, 59, tzinfo=current.tzinfo)
        new_events.append(e)

        current += timedelta(days=1)
        current = datetime(current.year, current.month, current.day, 0, 0, 0, tzinfo=current.tzinfo)

    num_events = len(new_events)
    for i, e in enumerate(new_events, start=1):
        if include_duration:
            e["duration"] = get_duration_string(e["start"], e["end"])

        if num_events > 1:
            e["part"] = f"{i}/{num_events}"

    return new_events

def get_key(event):
    duration = event["end"] - event["start"]

    return (
        event["event"].sharedUID(),
        event["title"],
        event.get("duration", ""),
        event.get("part", ""),
        duration.seconds)

def import_to_org(events, output_file,
                  include_end_time=False,
                  include_duration=False):
    org_data = PyOrgMode.OrgDataStructure()

    transformed_events = []
    for event in events:
        transformed_events += transform_event(event, include_duration=include_duration)

    grouped_events = {}
    for event in transformed_events:
        key = get_key(event)
        grouped_events[key] = grouped_events.get(key, []) + [event]

    for event_group in grouped_events.values():
        add_events(org_data, event_group, include_end_time=include_end_time)

    data = str(org_data.root)
    open(os.path.expanduser(output_file), "w", encoding="utf-8").write(data)

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

def cache_until_file_changes(function):
    cache = {}

    def helper(x):
        modified_time = os.stat(x).st_mtime
        cached_data = cache.get(x, None)
        if cached_data is None or cached_data[0] != modified_time:
            cached_data = (modified_time, function(x))
            cache[x] = cached_data

        return cached_data[1]

    return helper

@cache_until_file_changes
def collect_times_from_org_file(filename):
    results = []
    org = PyOrgMode.OrgDataStructure()
    org.load_from_file(os.path.expanduser(filename))
    nodes_to_process = [org.root]
    path = []
    while nodes_to_process:
        element = nodes_to_process.pop(0)
        if element is None:
            if path:
                path.pop(-1)

            continue

        if isinstance(element, PyOrgMode.OrgNode.Element):
            nodes_to_process = element.content + [None] + nodes_to_process
            path.append(clean_heading(element.heading))
            continue

        elif isinstance(element, PyOrgMode.OrgDrawer.Element):
            copied_path = tuple(path)
            for line in element.content:
                if not isinstance(line, str):
                    continue

                mo = CLOCK_PATTERN.match(line)
                if mo:
                    start = datetime.strptime(mo.group("start"), "%Y-%m-%d %a %H:%M").replace(tzinfo=TIMEZONE)
                    end = datetime.strptime(mo.group("end"), "%Y-%m-%d %a %H:%M").replace(tzinfo=TIMEZONE)
                else:
                    mo = INCOMPLETE_CLOCK_PATTERN.match(line)
                    if not mo:
                        continue

                    start = datetime.strptime(mo.group("start"), "%Y-%m-%d %a %H:%M").replace(tzinfo=TIMEZONE)
                    end = "now"

                results.append(dict(kind="clocks", path=copied_path, start=start, end=end))

        elif isinstance(element, PyOrgMode.OrgSchedule.Element):
            closed = read_time_from_element(element, "closed")
            is_closed = False
            if closed:
                results.append(dict(kind="closed", path=list(path), start=closed, end=None))
                is_closed = True

            for w in ("deadline", "scheduled"):
                dt = read_time_from_element(element, w)
                if dt:
                    results.append(dict(kind=w, path=list(path), start=dt, end=None))
                    if not is_closed:
                        results.append(dict(kind="active-" + w, path=list(path), start=dt, end=None))

    return results

def collect_times_from_org_files(files):
    results = []
    for f in files:
        results += collect_times_from_org_file(f)

    return results
