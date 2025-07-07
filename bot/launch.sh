#!/bin/bash

cd "$(dirname "$0")"

SESSION_NAME="musicbot"
BOT_SCRIPT="bot.py"
VENV_DIR="venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS_FILE="requirements.txt"

# --- Setup Function ---
# Creates the virtual environment and installs dependencies if needed.
setup_environment() {
    echo "--- Checking Environment Setup ---"
    if ! command -v ffmpeg &> /dev/null
    then
        echo "ffmpeg could not be found, attempting to install..."
        apt-get update && apt-get install -y ffmpeg
        if [ $? -ne 0 ]; then
            echo "Error: Failed to install ffmpeg. Please install it manually and try again."
            exit 1
        fi
    fi

    if ! dpkg -s libopus-dev &> /dev/null; then
        echo "libopus-dev could not be found, attempting to install..."
        apt-get update && apt-get install -y libopus-dev
        if [ $? -ne 0 ]; then
            echo "Error: Failed to install libopus-dev. Please install it manually and try again."
            exit 1
        fi
    fi

    if [ ! -d "$VENV_DIR" ]; then
        echo "Virtual environment not found. Creating one..."
        python3 -m venv "$VENV_DIR"
        if [ $? -ne 0 ]; then
            echo "Error: Failed to create virtual environment."
            exit 1
        fi
        echo "Virtual environment created."
    fi

    if [ ! -f "$VENV_PYTHON" ]; then
        echo "Error: Python executable not found in virtual environment."
        exit 1
    fi

    echo "Installing/updating dependencies from $REQUIREMENTS_FILE..."
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE" --no-cache-dir
    "$VENV_PYTHON" -m pip install --upgrade --force-reinstall yt-dlp
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies."
        exit 1
    fi
    echo "Dependencies are up to date."
    
    echo "Creating __init__.py files..."
    touch cogs/__init__.py
    touch utils/__init__.py
    
    echo "Making scripts executable..."
    chmod +x bot.py
    chmod +x cogs/*.py
    chmod +x utils/*.py
    chmod +x config.py
    
    
    echo "---------------------------------"
}


# --- Bot Control Functions ---
start_bot() {
    # Run the cache cleaner
    echo "Running audio cache cleaner..."
    "$VENV_PYTHON" "utils/cleaner.py"

    if screen -list | grep -q "$SESSION_NAME"; then
        echo "Bot is already running."
        exit 1
    fi

    if [ ! -f "$BOT_SCRIPT" ]; then
        echo "Error: Bot script not found at '$BOT_SCRIPT'."
        exit 1
    fi
    
    echo "Starting bot in a new screen session named '$SESSION_NAME'..."
    screen -dmS "$SESSION_NAME" bash -c "$VENV_PYTHON $BOT_SCRIPT &> bot.log"
    
    if screen -list | grep -q "$SESSION_NAME"; then
        echo "Bot is now running in the background."
        echo "Use './launch.sh attach' to view the bot's console."
    else
        echo "Error: Failed to start the bot. It might have crashed."
        echo "Try running it directly to see errors: $VENV_PYTHON $BOT_SCRIPT"
        exit 1
    fi
}

stop_bot() {
    if screen -list | grep -q "$SESSION_NAME"; then
        echo "Stopping bot session '$SESSION_NAME'..."
        screen -S "$SESSION_NAME" -X quit
        echo "Session stopped."
    else
        echo "Bot is not currently running."
    fi
}

attach_to_console() {
    echo "Displaying last 1000 lines of bot.log:"
    tail -n 1000 bot.log
    echo "---------------------------------"
    if screen -list | grep -q "$SESSION_NAME"; then
        echo "Attaching to session '$SESSION_NAME'. Press Ctrl+A then D to detach."
        screen -r "$SESSION_NAME"
    else
        echo "Bot is not running."
    fi
}

# --- Main Script Logic ---
case "$1" in
    start)
        setup_environment
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        stop_bot
        sleep 2
        setup_environment
        start_bot
        ;;
    attach)
        attach_to_console
        ;;
    setup)
        setup_environment
        echo "Setup complete. You can now start the bot with './launch.sh start'"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|attach|setup}"
        exit 1
        ;;
esac

exit 0
