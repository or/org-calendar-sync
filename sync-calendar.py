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

def create_element(events):
    event = events[0]
    element = PyOrgMode.OrgNode.Element()
    element.level = 1
    element.heading = fix_title(event.title()) + "            "
    element.tags = [convert_to_tag(event.calendar().title())]

    drawer = PyOrgMode.OrgDrawer.Element("SCHEDULE")
    element.append_clean(drawer)

    for e in events:
        start = dateparser.parse(str(e.startDate())).astimezone(pytz.timezone("Europe/Berlin"))
        end = dateparser.parse(str(e.endDate())).astimezone(pytz.timezone("Europe/Berlin"))
        if end.hour == 0 and end.minute == 0 and end.second == 0:
            end -= timedelta(seconds=1)

        drawer.append("<{start}>--<{end}>"
                      .format(start=start.strftime(ORG_TIME_FORMAT),
                              end=end.strftime(ORG_TIME_FORMAT)))

    return element

def add_events(org_data, events):
    element = create_element(events)
    if element:
        org_data.root.append_clean(element)
        org_data.root.append_clean("\n")

def get_key(event):
    uid = event.sharedUID()
    return (uid,)

def import_to_org(output_file, events):
    org_data = PyOrgMode.OrgDataStructure()
    grouped_events = {}
    for event in events:
        key = get_key(event)
        grouped_events[key] = grouped_events.get(key, []) + [event]

    for event_group in grouped_events.values():
        add_events(org_data, event_group)

    open(os.path.expanduser(output_file), "w", encoding="utf-8").write(str(org_data.root))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-file", "-o", default="~/org/calendar.org",
                        help="the org file to write")
    parser.add_argument("--num-days", "-n", default=30, type=int,
                        help="the number of days before and after today to include")

    args = parser.parse_args()
    events = get_events(args)

    import_to_org(args.output_file, events)
