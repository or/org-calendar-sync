def merge_ics_files(calendar_name, calendar_description, files):
    data = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//xor//merger v1.0//EN
CALSCALE:GREGORIAN
X-WR-CALNAME;VALUE=TEXT:{calendar_name}
X-WR-CALDESC;VALUE=TEXT:{calendar_description}
"""
    for f in files:
        for line in open(f):
            if line.startswith("BEGIN:VCALENDAR") or \
               line.startswith("END:VCALENDAR") or \
               line.split(":", 1)[0] in ("VERSION", "PRODID", "CALSCALE"):
                continue
            data += line

    data += "END:VCALENDAR\n"

    return data
