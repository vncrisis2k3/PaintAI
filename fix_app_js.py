#!/usr/bin/env python3
"""Fix app.js encoding"""

# Read app.js in binary
with open('static/app.js', 'rb') as f:
    content = f.read()

# The corrupted UTF-8 bytes sequence - look for specific patterns
# We need to find 'AI' followed by corrupted Vietnamese
corrupted_pattern = b"'AI"

# Find all lines containing the pattern
lines = content.split(b'\n')
for i, line in enumerate(lines):
    # Look around line 601 where we know the problem is
    if i >= 595 and i <= 610:
        if b"'AI" in line and (b'error' in line or b'toast' in line):
            # Check if it has non-ASCII high bytes beyond normal UTF-8
            high_bytes = [b for b in line if b > 200]  # Mojibake usually has bytes > 200
            if len(high_bytes) > 5:
                print(f"Found corrupted line {i+1}")
                print(f"Current: {line}")
                # Create fixed line
                fixed_line = b"        showToast('AI \xc4\x91ang x\xe1\xbb\xad l\xc3\xbd, vui l\xc3\xb2ng ch\xe1\xbb\x9d k\xe1\xba\xbft qu\xe1\xba\xa3.', 'error');"
                lines[i] = fixed_line
                print(f"Fixed: {fixed_line}")

# Write back
with open('static/app.js', 'wb') as f:
    f.write(b'\n'.join(lines))

print("Done!")
