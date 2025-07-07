import os
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    handlers=[
        logging.FileHandler("cleaner.log"),
        logging.StreamHandler()
    ]
)

def clean_audio_cache(cache_dir="audio_cache", max_age_hours=24):
    """
    Removes files from the audio cache directory that are older than max_age_hours.
    """
    if not os.path.isdir(cache_dir):
        logging.warning(f"Cache directory '{cache_dir}' not found.")
        return

    logging.info(f"Starting audio cache cleanup for directory: {cache_dir}")
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0

    for filename in os.listdir(cache_dir):
        file_path = os.path.join(cache_dir, filename)
        try:
            if os.path.isfile(file_path):
                file_age = now - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    os.remove(file_path)
                    logging.info(f"Deleted old cache file: {filename}")
                    deleted_count += 1
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")

    logging.info(f"Cleanup complete. Deleted {deleted_count} old file(s).")

if __name__ == "__main__":
    # The default cache directory is 'audio_cache' in the same directory as the script.
    # You can change this if your bot's structure is different.
    clean_audio_cache()
