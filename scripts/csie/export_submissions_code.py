#!/usr/bin/env python3
"""Export all submission source code from a contest"""

import gevent.monkey
gevent.monkey.patch_all()

import argparse
import os
from pathlib import Path

from cms.db import SessionGen, Contest, Token
from cms.db.filecacher import FileCacher
from cms.grading.languagemanager import get_language

parser = argparse.ArgumentParser(description="Export all submission source code")
parser.add_argument("contest_id", type=int, help="Contest ID")
parser.add_argument("--output-dir", dest="output_dir", default="submissions_code", help="Output directory (default: submissions_code)")

args = parser.parse_args()

output_path = Path(args.output_dir)
output_path.mkdir(parents=True, exist_ok=True)

file_cacher = FileCacher()

# Export all submission files
with SessionGen() as session:
    contest = session.query(Contest).get(args.contest_id)

    submission_count = 0
    for participation in contest.participations:
        # Skip hidden or unrestricted participations (e.g., admin test accounts)
        if participation.hidden or participation.unrestricted:
            continue

        username = participation.user.username

        for submission in participation.submissions:
            # Only include official submissions
            if not submission.official:
                continue

            submission_count += 1

            task_name = submission.task.name
            submission_id = submission.id
            timestamp_str = submission.timestamp.strftime('%Y%m%d_%H%M%S')

            # Find if this submission used a token
            token = session.query(Token).filter(
                Token.submission_id == submission.id
            ).first()
            token_flag = 'Y' if token else 'N'

            # Export all files (flattened structure)
            for filename, file_obj in submission.files.items():
                content = file_cacher.get_file_content(file_obj.digest)

                # Resolve language-specific filename for extension
                if submission.language and '.%l' in filename:
                    lang = get_language(submission.language)
                    ext = lang.source_extension
                else:
                    ext = filename.split('.')[-1] if '.' in filename else 'txt'

                # Flattened filename: id_username_task_timestamp_Y.ext (or _N if no token)
                output_filename = f"{submission_id}_{username}_{task_name}_{timestamp_str}_{token_flag}.{ext}"
                output_file = output_path / output_filename

                with open(output_file, 'wb') as f:
                    f.write(content)

                # Set file mtime to submission timestamp for easy sorting with ls -t
                submission_ts = submission.timestamp.timestamp()
                os.utime(output_file, (submission_ts, submission_ts))

    print(f"Exported {submission_count} submissions from {len(contest.participations)} participants")
    print()

print(f"Exported to: {output_path}")
