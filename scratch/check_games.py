import os
import json

log_dir = "logs"
for f in os.listdir(log_dir):
    if f.startswith("game_") and f.endswith(".jsonl"):
        filepath = os.path.join(log_dir, f)
        try:
            with open(filepath, "r") as file:
                first_line = file.readline()
                if first_line:
                    data = json.loads(first_line)
                    print(f"{f}: Model={data.get('model_name')}, Move={data.get('move_number')}, Time={data.get('elapsed_time')}")
        except Exception as e:
            print(f"Error reading {f}: {e}")
