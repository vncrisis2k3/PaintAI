#!/usr/bin/env python3
"""Complete Vietnamese encoding fix"""
import re

print("🔧 Fixing Vietnamese encoding...")

# ===== server.py fix =====
print("\n📝 Fixing server.py...")
with open('server.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Fix the corrupted message
old_messages = [
    "Không tìm thấy AI layer mask tại tọa độ click này. Hãy click gần vùng đã được AI phân tách.",
    "KhÃ´ng tÃ¬m tháº¥y AI layer mask táº¡i tá»a Ä'á»™ click nÃ y. HÃ£y click gáº§n vÃ¹ng Ä'Ã£ Ä'Æ°á»£c AI phÃ¢n tÃ¡ch.",
]

correct_message = "Không tìm thấy AI layer mask tại tọa độ click này. Hãy click gần vùng đã được AI phân tách."

for old in old_messages:
    if old in content:
        content = content.replace(old, correct_message)

with open('server.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("✓ server.py fixed")

# ===== app.js fix =====
print("📝 Fixing static/app.js...")
with open('static/app.js', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Fix line 601 area - AI processing message
pattern = r"showToast\('AI [^']*xử lý[^']*'\s*,\s*'error'\)"
correct = "showToast('AI đang xử lý, vui lòng chờ kết quả.', 'error')"

content = re.sub(pattern, correct, content)

# Also try direct replacement if pattern doesn't match
old_msg = "showToast('AI "
if old_msg in content:
    lines = content.split('\n')
    for i in range(len(lines)):
        if "showToast('AI " in lines[i] and "'error'" in lines[i] and i > 595 and i < 610:
            lines[i] = "        showToast('AI đang xử lý, vui lòng chờ kết quả.', 'error');"
    content = '\n'.join(lines)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("✓ app.js fixed")

print("\n✅ Vietnamese encoding fix completed!")
