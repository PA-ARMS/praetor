#!/bin/bash
# Auto-process script - Processes cases as they're downloaded
# Run this in a separate terminal to process cases continuously

echo "Starting auto-process mode..."
echo "This will continuously check for new cases and process them"
echo "Press Ctrl+C to stop"
echo ""

cd "$(dirname "$0")/.."

while true; do
    echo "$(date): Checking for new cases..."
    python scripts/process_scenarios_batch.py --max-cases 1000
    
    echo "$(date): Waiting 5 minutes before next check..."
    sleep 300  # Wait 5 minutes
done

