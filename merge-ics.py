#!/usr/bin/env python3
import argparse

from sync_org_calendar.ics_merger import merge_ics_files

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--calendar-name", "-n", default="Output", help="the calendar name")
    parser.add_argument("--calendar-description", "-d", default="Description", help="the calendar description")
    parser.add_argument("--output", "-o", required=True, help="output file")
    parser.add_argument("files", nargs="+", help="the files to merge")

    args = parser.parse_args()
    data = merge_ics_files(args.calendar_name, args.calendar_description, args.files)
    with open(args.output, "w") as f:
        f.write(data)
