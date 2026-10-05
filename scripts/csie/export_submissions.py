#!/usr/bin/env python3
"""Export submission and token usage data for analysis"""

import gevent.monkey
gevent.monkey.patch_all()

import argparse
import csv

from cms.db import SessionGen, Contest, Submission, Token

parser = argparse.ArgumentParser(description="Export submission and token usage data")
parser.add_argument("contest_id", type=int, help="Contest ID")
parser.add_argument("--output", default="submissions.csv", help="Output CSV file (default: submissions.csv)")

args = parser.parse_args()

# Query submissions and tokens
with SessionGen() as session:
    contest = session.query(Contest).get(args.contest_id)

    data = []
    for participation in contest.participations:
        # Skip hidden or unrestricted participations (e.g., admin test accounts)
        if participation.hidden or participation.unrestricted:
            continue

        username = participation.user.username

        for submission in participation.submissions:
            # Only include official submissions
            if not submission.official:
                continue
            # Find if this submission used a token
            token = session.query(Token).filter(
                Token.submission_id == submission.id
            ).first()

            data.append({
                'submission_id': submission.id,
                'username': username,
                'task_name': submission.task.name,
                'submission_timestamp': submission.timestamp.isoformat(),
                'used_token': token is not None,
                'token_timestamp': token.timestamp.isoformat() if token else ''
            })

    print(f"Collected {len(data)} submissions from {len(contest.participations)} participants")
    print()

# Write output
with open(args.output, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'submission_id', 'username', 'task_name',
        'submission_timestamp', 'used_token', 'token_timestamp'
    ])
    writer.writeheader()
    writer.writerows(data)

print(f"Exported to: {args.output}")
