import json

LOG_FILE = r"C:\Users\Admin\.gemini\antigravity\brain\4b0ee8da-1cfb-410a-ac03-5cc9c334f494\.system_generated\logs\transcript_full.jsonl"
OUTPUT_FILE = r"C:\Users\Admin\OneDrive\Desktop\smartrecipe\templates\recipes\generate.html"

print("Scanning memory banks directly...")

best_content = None

try:
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                if 'type' in data and data['type'] == 'VIEW_FILE':
                    content = data.get('content', '')
                    if 'generate.html' in content and '<!-- ═══ RECIPE HEADER ═══════════════════════════════════════ -->' in content:
                        # Extract the actual file content from the VIEW_FILE output.
                        # The VIEW_FILE output contains a line number prefix like "45: <original_line>"
                        # We need to strip that.
                        lines = content.split('\n')
                        reconstructed = []
                        for l in lines:
                            if ': ' in l[:10]:
                                try:
                                    int(l.split(':', 1)[0])
                                    reconstructed.append(l.split(': ', 1)[1])
                                except ValueError:
                                    reconstructed.append(l)
                            else:
                                reconstructed.append(l)
                        
                        full_text = '\n'.join(reconstructed)
                        if '<!-- NUTRITION CARD -->' in full_text and 'cooking-overlay' in full_text:
                            best_content = full_text
            except Exception:
                pass
except Exception as e:
    print(f"Error reading log: {e}")

if best_content:
    print("FOUND YOUR LOST DESIGN FROM THE LOGS!")
    with open("recover_test.html", 'w', encoding='utf-8') as f:
        f.write(best_content)
    print("Saved to recover_test.html")
else:
    print("Could not extract it automatically.")
