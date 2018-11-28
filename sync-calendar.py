#!/usr/bin/env python3
import argparse
import dateparser
import os.path
import pytz
from datetime import datetime, timedelta
from EventKit import EKEventStore, EKEntityMaskEvent, NSDate
from PyOrgMode import PyOrgMode

ORG_TIME_FORMAT = "%Y-%m-%d %a %H:%M"

def get_events(args):
    store = EKEventStore.alloc()
    store.initWithAccessToEntityTypes_(EKEntityMaskEvent)

    start_time = datetime.now() - timedelta(days=args.num_days)
    end_time = datetime.now() + timedelta(days=args.num_days)
    nsdate = NSDate.date()
    start = NSDate.initWithTimeIntervalSince1970_(nsdate, start_time.timestamp())
    end = NSDate.initWithTimeIntervalSince1970_(nsdate, end_time.timestamp())

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(start, end, store.allCalendars())
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

def create_element(args, events):
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
        if args.include_end_time:
            end = e["end"]
            if (end.hour, end.minute, end.second) == (0, 0, 0):
                end -= timedelta(seconds=1)

            drawer.append("<{start}>--<{end}>".format(
                start=start.strftime(ORG_TIME_FORMAT),
                end=end.strftime(ORG_TIME_FORMAT)))
        else:
            drawer.append("<{start}>".format(start=start.strftime(ORG_TIME_FORMAT)))

    return element

def add_events(args, org_data, events):
    element = create_element(args, events)
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

def transform_event(args, event):
    new_events = []
    start = dateparser.parse(str(event.startDate())).astimezone(pytz.timezone("Europe/Berlin"))
    end = dateparser.parse(str(event.endDate())).astimezone(pytz.timezone("Europe/Berlin"))

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
        if args.include_duration:
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

def import_to_org(args, events):
    org_data = PyOrgMode.OrgDataStructure()

    transformed_events = []
    for event in events:
        transformed_events += transform_event(args, event)

    grouped_events = {}
    for event in transformed_events:
        key = get_key(event)
        grouped_events[key] = grouped_events.get(key, []) + [event]

    for event_group in grouped_events.values():
        add_events(args, org_data, event_group)

    open(os.path.expanduser(args.output_file), "w", encoding="utf-8").write(str(org_data.root))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-file", "-o", default="~/org/calendar.org",
                        help="the org file to write")
    parser.add_argument("--num-days", "-n", default=30, type=int,
                        help="the number of days before and after today to include")
    parser.add_argument("--include-end-time", action="store_true",
                        help="include end time in scheduled time")
    parser.add_argument("--include-duration", action="store_true",
                        help="include duration in name")

    args = parser.parse_args()
    events = get_events(args)

    import_to_org(args, events)
