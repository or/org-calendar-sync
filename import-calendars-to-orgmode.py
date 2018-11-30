#!/usr/bin/env python3
import argparse
from datetime import datetime, timedelta

from orgmode_sync.orgmode_sync import get_events, import_to_org

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
    parser.add_argument("--include-calendars",
                        nargs="*",
                        default=None,
                        help="calendars to include, default is all of them")
    parser.add_argument("--exclude-calendars",
                        nargs="*",
                        default=None,
                        help="calendars to exclude")

    args = parser.parse_args()

    start_time = datetime.now() - timedelta(days=args.num_days)
    end_time = datetime.now() + timedelta(days=args.num_days)
    events = get_events(
        start_time,
        end_time,
        include_calendars=args.include_calendars,
        exclude_calendars=args.exclude_calendars)

    import_to_org(events,
                  output_file=args.output_file,
                  include_end_time=args.include_end_time,
                  include_duration=args.include_duration)
