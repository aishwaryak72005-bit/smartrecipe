import os
import re

TARGET_DIR = r"c:\Users\Admin\OneDrive\Desktop\smartrecipe\templates"

# Map old colors to new colors
REPLACEMENTS = {
    # Text colors
    r"#4c1d95": "#2C1810", # Deep Brown
    r"#6b46c1": "#C0392B", # Rasam Red
    r"#7c3aed": "#C0392B",
    r"#805ad5": "#F39C12", # Turmeric Gold
    r"#a855f7": "#C0392B",
    r"#ec4899": "#F39C12",
    r"#9333ea": "#C0392B",
    
    # Backgrounds
    r"#faf5ff": "#FAFAFA", # Rice White
    r"#fdf2f8": "#FAFAFA", # Rice White
    r"#f3e8ff": "#FDFEFE", # Coconut White

    # Borders & muted
    r"#ede9fe": "#E5E7EB", # Light gray/neutral border
    r"#fde68a": "#F39C12", # Light gold to Turmeric Gold
    
    # Button classes
    r"btn-purple": "btn-primary",
    
    # Specific gradients
    r"linear-gradient\(135deg,\s*#7c3aed\s*0%,\s*#a855f7\s*50%,\s*#ec4899\s*100%\)": "linear-gradient(135deg, #C0392B, #F39C12)",
    r"linear-gradient\(135deg,\s*#7c3aed,\s*#a855f7,\s*#ec4899\)": "linear-gradient(135deg, #C0392B, #F39C12)",
    r"linear-gradient\(135deg,\s*#6b46c1,\s*#805ad5\)": "linear-gradient(135deg, #C0392B, #F39C12)",
    r"linear-gradient\(135deg,\s*#6b46c1,\s*#ec4899\)": "linear-gradient(135deg, #C0392B, #F39C12)",
    r"linear-gradient\(135deg,#7c3aed,#a855f7\)": "linear-gradient(135deg, #C0392B, #F39C12)",
    r"linear-gradient\(135deg,#ec4899,#f472b6\)": "linear-gradient(135deg, #C0392B, #F39C12)",
    r"linear-gradient\(135deg,#6366f1,#818cf8\)": "linear-gradient(135deg, #27AE60, #2ECC71)", # Use green for variety
    r"linear-gradient\(135deg,#10b981,#34d399\)": "linear-gradient(135deg, #27AE60, #2ECC71)",
}

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old_pat, new_str in REPLACEMENTS.items():
        new_content = re.sub(old_pat, new_str, new_content, flags=re.IGNORECASE)
        
    # Extra fix for any remaining linear-gradients that were missed due to spacing
    new_content = re.sub(
        r"linear-gradient\(\s*135deg\s*,\s*#faf5ff\s*,\s*#fdf2f8\s*\)",
        "linear-gradient(135deg, #FAFAFA, #FFFFFF)",
        new_content, flags=re.IGNORECASE
    )
    new_content = re.sub(
        r"linear-gradient\(135deg,#faf5ff,#fdf2f8\)",
        "linear-gradient(135deg, #FAFAFA, #FFFFFF)",
        new_content, flags=re.IGNORECASE
    )
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, _, files in os.walk(TARGET_DIR):
    for file in files:
        if file.endswith(".html"):
            process_file(os.path.join(root, file))
