import sqlite3
import logging
from datetime import datetime

DB_PATH = "self_healing.db"

def initialize_db():
    """Creates the database and the log table if they don't exist."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS healing_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event TEXT NOT NULL,
                    details TEXT
                )
            """)
            conn.commit()
            logging.info("Self-healing database initialized successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")

def log_healing_event(event, details=""):
    """Logs a self-healing event to the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO healing_log (timestamp, event, details) VALUES (?, ?, ?)",
                (timestamp, event, details)
            )
            conn.commit()
            logging.info(f"Logged healing event: {event}")
    except sqlite3.Error as e:
        logging.error(f"Failed to log healing event: {e}")

if __name__ == '__main__':
    initialize_db()
    log_healing_event("Test Event", "This is a test of the self-healing log.")
    print("Database initialized and test event logged.")
