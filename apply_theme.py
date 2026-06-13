import os
import re

TARGET_DIR = r"c:\Users\Admin\OneDrive\Desktop\smartrecipe\templates"

REPLACEMENTS = {
    # Replace previous primary greens with Minty Breeze Primary (#059669)
    r"(?i)#22C55E": "#059669",
    r"(?i)#10B981": "#059669",
    
    # Replace secondary orange with Soft Mint (#A7F3D0)
    r"(?i)#F97316": "#A7F3D0",

    # Replace accent yellow with Deep Pine (#064E3B)
    r"(?i)#FBBF24": "#064E3B",

    # Replace background cream/slate with Soft White (#F8FAFC)
    r"(?i)#FFF8F0": "#F8FAFC",
    r"(?i)#FEF3C7": "#E2E8F0", # Reset card accents to neutral slate
}

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old_pat, new_str in REPLACEMENTS.items():
        new_content = re.sub(old_pat, new_str, new_content)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, _, files in os.walk(TARGET_DIR):
    for file in files:
        if file.endswith(".html"):
            process_file(os.path.join(root, file))

print("Minty Breeze Theme Applied Successfully!")
