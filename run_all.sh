#!/usr/bin/env bash
# One-shot pipeline: unit tests -> full benchmark -> charts.
# Usage: ./run_all.sh [port] [config_dir]
set -euo pipefail

PORT="${1:-50000}"
CONFIG_DIR="${2:-TestConfigs}"

chmod +x ds-server ds-client ds-mermaid

echo "==> Unit tests"
python3 -m pytest tests -q

echo "==> Benchmark ($CONFIG_DIR, port $PORT)"
python3 ds_test.py "python3 client.py" -n -p "$PORT" -c "$CONFIG_DIR"

echo "==> Charts"
if python3 -c "import matplotlib" 2>/dev/null; then
    python3 plot_results.py
else
    echo "matplotlib not installed, skipping (pip install matplotlib)"
fi
