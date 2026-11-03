"""
make_submission.py - build submission.zip for the Udacity "Zip File" upload.

Includes the project with the populated .env and any screenshots in
screenshots/. Leaves out secrets (aws.txt) and build output (build/,
node_modules/, cdk.out/, agentcore/.cli/, caches, virtualenvs).

Usage:  python make_submission.py      -> starter/submission.zip
Then right-click submission.zip in the Explorer -> Download.
"""

import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'submission.zip')
SKIP_DIRS = {'build', 'node_modules', 'cdk.out', '.cli', '__pycache__', 'venv', '.venv', '.git'}
SKIP_FILES = {'aws.txt', 'submission.zip'}   # aws.txt holds AWS keys - never submit it

if not os.path.exists(os.path.join(HERE, '.env')):
    sys.exit(".env not found - the submission needs the populated .env")

names = []
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name in SKIP_FILES or name.endswith('.pyc'):
                continue
            path = os.path.join(root, name)
            arcname = os.path.join('starter', os.path.relpath(path, HERE)).replace(os.sep, '/')
            zf.write(path, arcname)
            names.append(arcname)

assert not any(n.endswith('/aws.txt') for n in names), "aws.txt must not be in the zip"
shots = [n for n in names if n.startswith('starter/screenshots/')]
print(f"submission.zip: {len(names)} files, {os.path.getsize(OUT) // 1024} KB")
for must in ('starter/.env', 'starter/src/agent_orchestrator.py'):
    print(f"  {'OK     ' if must in names else 'MISSING'} {must}")
print(f"  {'OK     ' if shots else 'MISSING'} screenshots/ ({len(shots)} files)")
if not shots:
    print("  -> drag your screenshots into a 'screenshots' folder here, then run again")
print("Download: right-click submission.zip in the Explorer -> Download")
