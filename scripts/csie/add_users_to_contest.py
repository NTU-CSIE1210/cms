#!/usr/bin/env python3
"""Add users from YAML to a contest, optionally with bonus tokens"""
import argparse
import csv
import subprocess
import sys

import yaml

parser = argparse.ArgumentParser(description="Add users to a contest")
parser.add_argument("contest_id", type=int, help="Contest ID")
parser.add_argument("yaml_file", help="Path to contest.yaml")
parser.add_argument("--bonus-tokens", help="CSV file with bonus tokens (id,midterm_tokens,...)")
parser.add_argument("--base-tokens", type=int, default=10, help="Base token count (default: 10)")

args = parser.parse_args()

# Load users from YAML
with open(args.yaml_file, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# Load bonus tokens from CSV if provided
bonus_map = {}
if args.bonus_tokens:
    with open(args.bonus_tokens, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        # Detect the bonus token column
        columns = reader.fieldnames
        bonus_col = None
        for col in columns:
            if 'token' in col.lower() or 'bonus' in col.lower():
                bonus_col = col
                break

        if bonus_col is None:
            print(f"Error: Cannot find token/bonus column in CSV. Columns: {columns}")
            sys.exit(1)

        for row in reader:
            username = row['id'].strip().lower()
            bonus_map[username] = int(row[bonus_col])

    print(f"Loaded bonus tokens for {len(bonus_map)} users (base={args.base_tokens}, bonus column='{bonus_col}')")
    print()

success, skipped, failed = 0, 0, 0

# Add each user to the contest
for user in data['users']:
    username = user['username']

    cmd = ['cmsAddParticipation', '-c', str(args.contest_id), username]

    # If user has bonus tokens, add --update and --token-gen-initial
    if username in bonus_map:
        bonus = bonus_map[username]
        final_tokens = args.base_tokens + bonus
        cmd.extend(['--update', '--token-gen-initial', str(final_tokens)])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        if username in bonus_map:
            print(f"{username}: added/updated with {bonus:2d} bonus → {final_tokens:2d} total tokens")
        else:
            print(f"{username}: added")
        success += 1
    elif "already exists" in result.stderr:
        print(f"{username}: skipped")
        skipped += 1
    else:
        print(f"{username}: failed - {result.stderr.strip()}")
        failed += 1

print(f"\nTotal: {success} added/updated, {skipped} skipped, {failed} failed")
