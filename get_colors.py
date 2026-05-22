import json

with open('mauson.txt') as f:
    data = json.load(f)
    
colors = data['data']['colors']
print(f"Total colors: {len(colors)}\n")
for c in colors[:40]:
    print(f"{c['paint_code']}: {c['hex_code']}")
