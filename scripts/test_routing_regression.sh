#!/bin/bash
# Regression test to detect routing changes over time
# Usage: ./scripts/test_routing_regression.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASELINE_FILE="$SCRIPT_DIR/routing_baseline.json"
CURRENT_RESULTS="$SCRIPT_DIR/routing_test_results.json"

echo "=== LiteLLM Routing Regression Test ==="
echo ""

# Run current tests
echo "Running routing tests..."
python3 "$SCRIPT_DIR/test_routing_enhanced.py"

# Check if baseline exists
if [ ! -f "$BASELINE_FILE" ]; then
    echo ""
    echo "No baseline found. Saving current results as baseline..."
    cp "$CURRENT_RESULTS" "$BASELINE_FILE"
    echo "Baseline saved to: $BASELINE_FILE"
    exit 0
fi

echo ""
echo "Comparing with baseline..."
echo ""

# Extract key metrics from both files
BASELINE_COMPLEX=$(jq -r '.summary.COMPLEX' "$BASELINE_FILE")
CURRENT_COMPLEX=$(jq -r '.summary.COMPLEX' "$CURRENT_RESULTS")

BASELINE_REASONING=$(jq -r '.summary.REASONING' "$BASELINE_FILE")
CURRENT_REASONING=$(jq -r '.summary.REASONING' "$CURRENT_RESULTS")

BASELINE_SIMPLE=$(jq -r '.summary.SIMPLE' "$BASELINE_FILE")
CURRENT_SIMPLE=$(jq -r '.summary.SIMPLE' "$CURRENT_RESULTS")

BASELINE_ERRORS=$(jq -r '.summary.ERRORS' "$BASELINE_FILE")
CURRENT_ERRORS=$(jq -r '.summary.ERRORS' "$CURRENT_RESULTS")

echo "Metric           | Baseline | Current | Change | Status"
echo "-" | head -c 65
echo ""

# Function to compare and report changes
compare_metric() {
    local name=$1
    local baseline=$2
    local current=$3
    
    if [ "$baseline" = "null" ] || [ "$current" = "null" ]; then
        echo "Unable to parse metrics"
        return
    fi
    
    local change=$((current - baseline))
    local change_pct=0
    if [ "$baseline" -gt 0 ]; then
        change_pct=$(( (change * 100) / baseline ))
    fi
    
    local status="✓"
    if [ "$change_pct" -gt 10 ] || [ "$change_pct" -lt -10 ]; then
        status="⚠️"
    fi
    
    printf "%-15s | %8d | %7d | %+5d%% | %s\n" "$name" "$baseline" "$current" "$change_pct" "$status"
}

compare_metric "COMPLEX (Sonnet)" "$BASELINE_COMPLEX" "$CURRENT_COMPLEX"
compare_metric "REASONING (Opus)" "$BASELINE_REASONING" "$CURRENT_REASONING"
compare_metric "SIMPLE (Haiku)" "$BASELINE_SIMPLE" "$CURRENT_SIMPLE"
compare_metric "Errors" "$BASELINE_ERRORS" "$CURRENT_ERRORS"

echo ""
echo "✓ Regression test complete"
