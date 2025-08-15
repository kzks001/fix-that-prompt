#!/bin/bash

# Launch Fix That Prompt Dashboard in borderless mode

# Start Flask server in background
echo "Starting Flask server..."
python app.py &
FLASK_PID=$!

# Wait for server to start
sleep 3

# Launch browser in app mode (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Launching dashboard in borderless mode..."
    open -a "Google Chrome" --args --app="http://localhost:5001" --disable-web-security --user-data-dir=/tmp/chrome-dashboard
    
    # Alternative: Use Safari
    # open -a "Safari" "http://localhost:5001"
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Launching dashboard in borderless mode..."
    google-chrome --app="http://localhost:5001" --disable-web-security --user-data-dir=/tmp/chrome-dashboard &
    
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    echo "Launching dashboard in borderless mode..."
    start chrome --app="http://localhost:5001" --disable-web-security --user-data-dir=%TEMP%\chrome-dashboard
fi

echo "Dashboard launched! Press Ctrl+C to stop the server."
echo "Flask server PID: $FLASK_PID"

# Wait for user to stop
trap "echo 'Stopping Flask server...'; kill $FLASK_PID; exit" INT
wait
