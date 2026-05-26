#!/usr/bin/env python3
"""Fix corrupted Vietnamese UTF-8 encoding in server.py and app.js"""

import re

# Fix server.py
print("Fixing server.py...")
with open('server.py', 'rb') as f:
    raw = f.read()

lines = raw.split(b'\n')
fixed_lines = []

for i, line in enumerate(lines):
    # Look for the line with corrupted message near ai_mask_not_found
    if b'ai_mask_not_found' in line:
        fixed_lines.append(line)
        # Next lines might be the message
        continue
    
    # Check for corrupted Vietnamese message
    if b'"message"' in line and b'AI' in line and b'click' in line:
        # Count high bytes (non-ASCII)
        high_count = sum(1 for byte in line if byte > 127)
        if high_count > 15:  # Likely corrupted
            # Replace with correct UTF-8 Vietnamese
            if b'mask' in line:
                line = b'                    "message": "Kh\xc3\xb4ng t\xc3\xacm th\xe1\xba\xa5y AI layer mask t\xe1\xba\xa1i t\xe1\xbb\x8da \xc4\x91\xe1\xbb\x99 click n\xc3\xa0y. H\xc3\xa3y click g\xe1\xba\xa7n v\xf9ng \xc4\x91\xc3\xa3 \xc4\x91\xc6\xb0\xe1\xbb\xa3c AI ph\xc3\xa2n t\xc3\xa1ch.",'
                print(f"  Fixed server.py line {i+1}: message")
    
    fixed_lines.append(line)

with open('server.py', 'wb') as f:
    f.write(b'\n'.join(fixed_lines))
print("server.py done")

# Fix app.js
print("Fixing app.js...")
with open('static/app.js', 'rb') as f:
    content = f.read()

lines = content.split(b'\n')
fixed = []

for i, line in enumerate(lines):
    # Look for the corrupted "xử lý" message
    if b"'AI" in line and b'click' in line and b'error' in line:
        high_count = sum(1 for byte in line if byte > 127)
        if high_count > 15:  # Likely corrupted
            line = b"        showToast('AI \xc4\x91ang x\xe1\xbb\xad l\xc3\xbd, vui l\xc3\xb2ng ch\xe1\xbb\x9d k\xe1\xba\xbft qu\xe1\xba\xa3.', 'error');"
            print(f"  Fixed app.js line {i+1}: AI processing message")
    
    fixed.append(line)

with open('static/app.js', 'wb') as f:
    f.write(b'\n'.join(fixed))
print("app.js done")

print("\nEncoding fix completed!")
