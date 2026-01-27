#!/bin/bash
# Tennis Predictor - Quick Start Guide
# Save this and run: bash tennis_quickstart.sh

echo "========================================="
echo "Tennis Predictor - Quick Start"
echo "========================================="

# Check Python
echo ""
echo "✓ Checking Python..."
python3 --version

# Install requirements
echo ""
echo "✓ Installing requirements..."
pip install -q lxml pandas requests 2>/dev/null
echo "  Done: lxml, pandas, requests"

# Run main predictor
echo ""
echo "✓ Running Tennis Predictor..."
echo "========================================="
python3 tennis_stats_predictor.py

echo ""
echo "✓ Done! Check out:"
echo "  - TENNIS_README.md for overview"
echo "  - TENNIS_PREDICTOR_SETUP.md for detailed setup"
echo "  - python tennis_examples.py for usage examples"
echo ""
echo "To integrate with betting APIs:"
echo "  export SGO_API_KEY='your_key'"
echo "  export RAPIDAPI_KEY='your_key'"
echo ""
