#!/usr/bin/env python3
"""Add users from YAML to a contest"""
import sys
import subprocess
import yaml

if len(sys.argv) != 3:
    print("Usage: add_users_to_contest.py <contest_id> <contest.yaml>")
    sys.exit(1)

contest_id = sys.argv[1]
yaml_file = sys.argv[2]

with open(yaml_file, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

success, skipped, failed = 0, 0, 0

# Add each user to the contest
for user in data['users']:
    username = user['username']
    result = subprocess.run(
        ['cmsAddParticipation', '-c', contest_id, username],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        print(f"{username}: added")
        success += 1
    elif "already exists" in result.stderr:
        print(f"{username}: skipped")
        skipped += 1
    else:
        print(f"{username}: failed")
        failed += 1

print(f"\nTotal: {success} added, {skipped} skipped, {failed} failed")
