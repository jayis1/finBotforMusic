import re
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
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                entry = parse_log_entry(line)
                if entry:
                    parsed_data.append(entry)
    except FileNotFoundError:
        print(f"Error: Log file not found at {file_path}")
    except Exception as e:
        print(f"Error reading or parsing log file: {e}")
    return parsed_data

if __name__ == "__main__":
    # Example usage: Create a dummy log file for testing
    dummy_log_content = """2025-07-06 10:00:00,123:INFO:root: Bot started successfully.
2025-07-06 10:00:01,456:WARNING:cogs.music: User not in voice channel.
2025-07-06 10:00:02,789:ERROR:cogs.youtube: Failed to fetch video info.
"""
    with open("dummy_bot_activity.log", "w", encoding="utf-8") as f:
        f.write(dummy_log_content)

    # Parse the dummy log file
    parsed_logs = parse_log_file("dummy_bot_activity.log")

    for log_entry in parsed_logs:
        print(f"Timestamp: {log_entry['timestamp']}, Level: {log_entry['level']}, Message: {log_entry['message']}")

    # Clean up dummy file
    import os
    os.remove("dummy_bot_activity.log")
