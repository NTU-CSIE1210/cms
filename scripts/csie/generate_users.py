#!/usr/bin/env python3
"""Generate CMS users from NTU Cool student list CSV"""
import csv
import secrets
import yaml
import sys
from xkcdpass import xkcd_password as xp

def generate_password():
    wordfile = xp.locate_wordfile()
    words = xp.generate_wordlist(
        wordfile=wordfile,
        min_length=4,
        max_length=6
    )
    # 3 words + 2 digits, e.g. "cage-shiny-pasta-42"
    password = xp.generate_xkcdpassword(words, numwords=3, delimiter='-')
    return password + '-' + str(secrets.randbelow(90) + 10)

def parse_name(full_name):
    """Extract Chinese name from format: '王小明 (WANG, XIAO-MING)'"""
    if '(' in full_name:
        return full_name.split('(')[0].strip()
    return full_name.strip()

if len(sys.argv) != 2:
    print("Usage: generate_users.py <student_csv>")
    sys.exit(1)

csv_file = sys.argv[1]
users = []
credentials = []

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        student_id = row['學號'].strip()
        username = student_id.lower()
        password = generate_password()
        chinese_name = parse_name(row['姓名'].strip())

        users.append({
            'username': username,
            'password': password,
            'first_name': student_id,
            'last_name': chinese_name
        })

        credentials.append({
            'student_id': student_id,
            'name': row['姓名'].strip(),
            'username': username,
            'password': password,
            'email': row['信箱'].strip()
        })

# Generate contest.yaml
with open('contest.yaml', 'w', encoding='utf-8') as f:
    yaml.dump({
        'name': 'students',
        'description': 'All Students',
        'tasks': [],
        'token_mode': 'disabled',
        'users': users
    }, f, allow_unicode=True, sort_keys=False)

# Generate credentials.csv
with open('credentials.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['student_id', 'name', 'username', 'password', 'email'])
    writer.writeheader()
    writer.writerows(credentials)

print(f"Generated {len(users)} users")
print("Output: contest.yaml, credentials.csv")
