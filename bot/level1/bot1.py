import os
import subprocess
import sys

def main():
    # Get the absolute path to the bot3.py script
    bot3_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'level2', 'level3', 'bot3.py'))
    
    # Start bot3.py as a subprocess
    try:
        print("Starting bot3.py...")
        subprocess.run([sys.executable, bot3_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error starting bot3.py: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()