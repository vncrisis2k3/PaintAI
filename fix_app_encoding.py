#!/usr/bin/env python3
"""Fix app.js encoding issue"""

with open('static/app.js', 'rb') as f:
    content = f.read()

# Replace the exact corrupted bytes
old = b"        showToast('AI \xc3\x84\xe2\x80\x98ang x\xc3\xa1\xc2\xbb\xc2\xad l\xc3\x83\xc2\xbd, vui l\xc3\x83\xc2\xb2ng ch\xc3\xa1\xc2\xbb\xc2\x9d k\xc3\xa1\xc2\xba\xc2\xbft qu\xc3\xa1\xc2\xba\xc2\xa3.', 'error');"
new = b"        showToast('AI \xc4\x91ang x\xe1\xbb\xad l\xc3\xbd, vui l\xc3\xb2ng ch\xc1\xb1\xc3\xb3 k\xe1\xba\xbft qu\xe1\xba\xa3.', 'error');"

if old in content:
    content = content.replace(old, new)
    with open('static/app.js', 'wb') as f:
        f.write(content)
    print("✓ Fixed app.js encoding")
else:
    print("✗ Pattern not found - trying alternative fix...")
    # Try to find and fix by looking for the corrupted pattern differently
    lines = content.split(b'\n')
    for i in range(len(lines)):
        if b"showToast('AI" in lines[i] and b'error' in lines[i] and i > 595 and i < 610:
            # Found the line, check if it's corrupted
            if b'\xc3\x84\xe2\x80\x98' in lines[i]:  # The corrupted "Ä'" sequence
                lines[i] = new + b'\r' if b'\r' in lines[i] else new
                print(f"✓ Fixed line {i+1}")
    
    with open('static/app.js', 'wb') as f:
        f.write(b'\n'.join(lines))
    print("✓ Fixed app.js via alternative method")
