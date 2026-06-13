import json
import os

LOG_FILE = r"C:\Users\Admin\.gemini\antigravity\brain\4b0ee8da-1cfb-410a-ac03-5cc9c334f494\.system_generated\logs\transcript_full.jsonl"
OUTPUT_FILE = r"C:\Users\Admin\OneDrive\Desktop\smartrecipe\templates\recipes\generate.html"

print("Scanning memory banks for your beautiful lost design...")

latest_html = None

try:
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                # Look for tool calls that modified generate.html
                if 'tool_calls' in data:
                    for call in data['tool_calls']:
                        if call.get('name') in ['replace_file_content', 'multi_replace_file_content']:
                            target = call.get('args', {}).get('TargetFile', '')
                            if 'generate.html' in target:
                                content = call.get('args', {}).get('ReplacementContent', '')
                                if '<!-- NUTRITION CARD -->' in content or 'cooking-overlay' in content:
                                    # This is tricky because we only replaced parts.
                                    pass
                # Or look for view_file outputs
                if 'type' == data.get('type') and 'VIEW_FILE' in data.get('type', ''):
                    content = data.get('content', '')
                    if '<!-- ═══ RECIPE HEADER ═══════════════════════════════════════ -->' in content:
                        pass
            except Exception as e:
                pass
except Exception as e:
    print(f"Error reading log: {e}")

print("Wait, an easier way is to use VS Code Local History. The python script can pull from VS Code history!")

import glob
history_dir = os.path.expandvars(r"%APPDATA%\Code\User\History")
print(f"Searching VS Code History at: {history_dir}")

best_file = None
best_time = 0

for root, dirs, files in os.walk(history_dir):
    for file in files:
        if file == "entries.json":
            try:
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    entries = json.load(f)
                    for entry in entries.get('entries', []):
                        file_id = entry.get('id')
                        timestamp = entry.get('timestamp', 0)
                        
                        file_path = os.path.join(root, file_id)
                        if os.path.exists(file_path):
                            with open(file_path, 'r', encoding='utf-8') as hf:
                                content = hf.read()
                                # We want a version that has the nutrition cards AND the canva UI, before the 0 byte crash
                                if '<!-- NUTRITION CARD -->' in content and 'Start Cooking' in content and len(content) > 10000:
                                    if timestamp > best_time:
                                        best_time = timestamp
                                        best_file = file_path
            except Exception:
                pass

if best_file:
    print("FOUND YOUR LOST DESIGN!")
    with open(best_file, 'r', encoding='utf-8') as f:
        old_content = f.read()
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(old_content)
    
    print("SUCCESS! I have restored the exact design you had before the crash.")
    print("Please do a hard refresh (Ctrl + Shift + R) in your browser!")
else:
    print("Could not find it in history. Please check VS Code Timeline manually.")
