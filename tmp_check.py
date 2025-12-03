from pathlib import Path
text = Path(''frontend/src/TimelineApp.vue'').read_text(encoding='utf-8', errors='replace')
print('lines', len(text.splitlines()))
for i,line in enumerate(text.splitlines(),1):
    if 730 <= i <= 780:
        print(f"{i}: {line}")
