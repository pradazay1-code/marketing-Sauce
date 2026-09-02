#!/usr/bin/env python3
"""
Clean a lead CSV before importing it into GoHighLevel.

Solves the duplicate-contact problem: GHL dedupes on import by exact phone
match, so "(508) 555-1234" and "+15085551234" become two contact records for
one person -- and each one runs the full voicemail sequence.

This normalizes every number to E.164, drops rows already sequenced, drops
anyone on the suppression list, and writes a clean file ready to import.

Usage
-----
  # dry run -- see what would be removed, change nothing
  python execution/dedupe_vm_list.py --input new_leads.csv

  # write the cleaned file and record the numbers as sent
  python execution/dedupe_vm_list.py --input new_leads.csv \
      --output clients/leads/ready_to_import.csv --commit

Files it maintains (created on first use)
-----------------------------------------
  clients/leads/vm-drop-history.csv      every number ever sequenced
  clients/leads/vm-drop-suppression.csv  opt-outs, DNC, do-not-contact

Only --commit writes to history. Run without it as often as you like.
"""

import argparse
import csv
import os
import re
import sys
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY = os.path.join(REPO, "clients", "leads", "vm-drop-history.csv")
SUPPRESSION = os.path.join(REPO, "clients", "leads", "vm-drop-suppression.csv")

# Column names we accept for each field, checked case- and space-insensitively.
PHONE_KEYS = {"phone", "phonenumber", "phone number", "mobile", "cell",
              "cellphone", "telephone", "primaryphone", "phone1"}
NAME_KEYS = {"firstname", "first name", "first", "fname", "name", "contact"}
BIZ_KEYS = {"company", "companyname", "company name", "business",
            "businessname", "business name", "organization"}


def norm_key(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").strip().lower())


def find_column(fieldnames, candidates):
    """Return the actual header whose normalized form is in candidates."""
    for f in fieldnames or []:
        k = norm_key(f)
        if k in candidates or k.replace(" ", "") in candidates:
            return f
    return None


def normalize_phone(raw):
    """
    US/Canada number -> E.164 (+1XXXXXXXXXX).

    Returns None for anything that cannot be a valid NANP number, which is
    what you want: a malformed number is a wasted drop, not a lead.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    # NANP: area code and exchange both start 2-9.
    if digits[0] in "01" or digits[3] in "01":
        return None
    return "+1" + digits


def load_phone_set(path):
    """Read a maintained CSV and return the set of normalized phones in it."""
    if not os.path.exists(path):
        return set()
    out = set()
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        col = find_column(reader.fieldnames, PHONE_KEYS)
        if not col:
            return out
        for row in reader:
            p = normalize_phone(row.get(col))
            if p:
                out.add(p)
    return out


def append_history(path, rows):
    """Append newly-sequenced numbers to the history file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if not exists:
            w.writerow(["phone", "first_name", "company", "date_sent"])
        today = date.today().isoformat()
        for r in rows:
            w.writerow([r["phone"], r["name"], r["company"], today])


def main():
    ap = argparse.ArgumentParser(
        description="Deduplicate and clean a lead CSV before GHL import.")
    ap.add_argument("--input", required=True, help="Raw lead CSV")
    ap.add_argument("--output", help="Where to write the cleaned CSV")
    ap.add_argument("--commit", action="store_true",
                    help="Write the output file and record numbers as sent")
    ap.add_argument("--history", default=HISTORY)
    ap.add_argument("--suppression", default=SUPPRESSION)
    args = ap.parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"Input not found: {args.input}")
    if args.commit and not args.output:
        sys.exit("--commit needs --output so there is a file to import.")

    history = load_phone_set(args.history)
    suppressed = load_phone_set(args.suppression)

    with open(args.input, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = reader.fieldnames or []

    phone_col = find_column(fields, PHONE_KEYS)
    if not phone_col:
        sys.exit(
            "No phone column found. Expected one of: "
            + ", ".join(sorted(PHONE_KEYS))
            + f"\nFound: {', '.join(fields)}"
        )
    name_col = find_column(fields, NAME_KEYS)
    biz_col = find_column(fields, BIZ_KEYS)

    kept, seen = [], set()
    n_invalid = n_dupe = n_history = n_suppressed = 0

    for row in rows:
        phone = normalize_phone(row.get(phone_col))
        if not phone:
            n_invalid += 1
            continue
        if phone in suppressed:
            n_suppressed += 1
            continue
        if phone in history:
            n_history += 1
            continue
        if phone in seen:
            n_dupe += 1
            continue
        seen.add(phone)
        kept.append({
            "phone": phone,
            "name": (row.get(name_col) or "").strip() if name_col else "",
            "company": (row.get(biz_col) or "").strip() if biz_col else "",
        })

    total = len(rows)
    print(f"\n  Read              {total} rows from {os.path.basename(args.input)}")
    print(f"  Invalid numbers   {n_invalid:>5}")
    print(f"  Dupes in file     {n_dupe:>5}")
    print(f"  Already sequenced {n_history:>5}")
    print(f"  Suppressed        {n_suppressed:>5}")
    print(f"  {'-' * 24}")
    print(f"  Ready to import   {len(kept):>5}\n")

    if not kept:
        print("  Nothing new to send.\n")
        return

    if not args.commit:
        print("  Dry run — nothing written. Add --output and --commit to write.\n")
        for r in kept[:5]:
            print(f"    {r['phone']}  {r['name']}  {r['company']}")
        if len(kept) > 5:
            print(f"    ... and {len(kept) - 5} more")
        print()
        return

    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".",
                exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["First Name", "Phone", "Company"])
        for r in kept:
            w.writerow([r["name"], r["phone"], r["company"]])

    append_history(args.history, kept)

    print(f"  Wrote   {args.output}")
    print(f"  Logged  {len(kept)} numbers to {os.path.relpath(args.history, REPO)}\n")
    print("  Import this file into GHL and tag the batch 'vm-drop'.\n")


if __name__ == "__main__":
    main()
