import re
import os
from datetime import datetime

def parse_log_entry(log_line: str) -> dict | None:
    """
    Parses a single log line into a dictionary of its components.
    Assumes log format: YYYY-MM-DD HH:MM:SS,ms:LEVEL:NAME: MESSAGE
    """
    match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}):([A-Z]+):([^:]+): (.*)', log_line)
    if match:
        timestamp_str, level, name, message = match.groups()
        try:
            # Parse timestamp, ignoring milliseconds for simplicity in datetime object
            dt_object = datetime.strptime(timestamp_str.split(',')[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt_object = None # Or handle more robustly if needed
        
        return {
            "timestamp": timestamp_str,
            "datetime": dt_object,
            "level": level,
            "name": name,
            "message": message.strip()
        }
    return None

def parse_log_file(file_path: str) -> list[dict]:
    """
    Reads a log file and parses each line into a list of dictionaries.
    """
    parsed_data = []
    if not os.path.exists(file_path):
        print(f"Warning: Log file not found at {file_path}")
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                entry = parse_log_entry(line)
                if entry:
                    parsed_data.append(entry)
    except Exception as e:
        print(f"Error reading or parsing log file {file_path}: {e}")
    return parsed_data

def main():
    bot6_dir = "/root/.local/bot6"
    log_files = {
        "bot_activity_log": os.path.join(bot6_dir, "bot_activity.log"),
        "bot_log": os.path.join(bot6_dir, "bot.log")
    }

    print("--- Parsing Bot Logs ---")
    for log_name, file_path in log_files.items():
        print(f"\nParsing {log_name} ({file_path})...")
        logs = parse_log_file(file_path)
        if logs:
            print(f"Found {len(logs)} entries.")
            # Print a summary or specific types of logs
            for entry in logs:
                if entry['level'] in ['ERROR', 'WARNING']:
                    print(f"[{entry['level']}] {entry['timestamp']} - {entry['name']}: {entry['message']}")
                elif "error" in entry['message'].lower() or "fail" in entry['message'].lower():
                    print(f"[{entry['level']}] {entry['timestamp']} - {entry['name']}: {entry['message']}")
        else:
            print("No log entries found or file does not exist.")

if __name__ == "__main__":
    main()
