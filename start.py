#!/usr/bin/env python3
import os
import subprocess

port = os.environ.get('PORT', '8080')
cmd = f'gunicorn app:app --bind 0.0.0.0:{port} --workers 1 --threads 2'
print(f"Starting on port {port}")
subprocess.run(cmd.split())
