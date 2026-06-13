import json

LOG_FILE = r"C:\Users\Admin\.gemini\antigravity\brain\4b0ee8da-1cfb-410a-ac03-5cc9c334f494\.system_generated\logs\transcript_full.jsonl"

with open(LOG_FILE, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get("type") == "PLANNER_RESPONSE":
                tool_calls = data.get("tool_calls", [])
                for call in tool_calls:
                    if call.get("name") in ["replace_file_content", "multi_replace_file_content"]:
                        args = call.get("args", {})
                        if "generate.html" in args.get("TargetFile", ""):
                            instruction = args.get("Instruction", "")
                            description = args.get("Description", "")
                            if "recipe card" in instruction.lower() or "recipe card" in description.lower() or "canva" in instruction.lower():
                                print("Found match!")
                                print("Instruction:", instruction)
                                print("Description:", description)
                                print("ReplacementContent:", str(args.get("ReplacementContent", ""))[:500])
                                print("-" * 40)
        except json.JSONDecodeError:
            pass
