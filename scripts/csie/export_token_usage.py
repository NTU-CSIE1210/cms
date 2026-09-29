#!/usr/bin/env python3
"""Export token usage statistics"""

import gevent.monkey
gevent.monkey.patch_all()

import argparse
import csv

import yaml

from cms.db import SessionGen, Contest, Token, Submission

parser = argparse.ArgumentParser(description="Export token usage statistics")
parser.add_argument("contest_id", type=int, help="Contest ID")
parser.add_argument("yaml_file", help="Path to contest.yaml")
parser.add_argument("--base-tokens", type=int, default=10, help="Base token count (default: 10)")
parser.add_argument("--output", default="token_usage.csv", help="Output CSV file (default: token_usage.csv)")

args = parser.parse_args()

# Load users from YAML
with open(args.yaml_file, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# Initialize token data for all users in YAML
token_data = {}
for user in data['users']:
    token_data[user['username']] = 0

print(f"Loaded {len(token_data)} users from YAML (base_tokens={args.base_tokens})")
print()

# Query token usage
with SessionGen() as session:
    contest = session.query(Contest).get(args.contest_id)
    for p in contest.participations:
        username = p.user.username
        if username in token_data:
            total_used = session.query(Token).join(Submission).filter(Submission.participation == p).count()
            bonus_used = max(0, total_used - args.base_tokens)
            token_data[username] = bonus_used

# Write output
with open(args.output, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'bonus_tokens_used'])
    for username in sorted(token_data.keys()):
        writer.writerow([username, token_data[username]])

print(f"Exported to: {args.output}")
