#!/bin/bash
# CONFIGURATION
RESULTS_DIR="results"

TARGET_THREAD=2

PYTHON_CMD="python3"

mkdir -p "$RESULTS_DIR"

echo "=================================================="
echo "   AUTOMATED COMPLET BENCHMARK  (Coeur #$TARGET_THREAD)"
echo "=================================================="

# 1. Topologie (Si lstopo est installé)
if command -v lstopo &> /dev/null; then
    echo "[INFO] Topology Captured.."
    lstopo --output-format png "$RESULTS_DIR/system_topology.png" --no-io
fi


# 1. Sequential test plot
echo ""
echo "--- PHASE 1 : Micro-Analyse (sequential mode) ---"
taskset -c $TARGET_THREAD $PYTHON_CMD run_micro_analysis_seq.py

# 2. Script to capture metrics perf and plot ipc vs size
echo ""
echo "--- PHASE 3 : Script Standard (CSV) ---"
taskset -c $TARGET_THREAD $PYTHON_CMD script.py

# 3. Random test plot 
echo ""
echo "--- PHASE 4 : Micro-Analyse (mode aleatoire) ---"
taskset -c $TARGET_THREAD $PYTHON_CMD run_micro_analysis_rand.py



# 3. Plot of sequential and random (to validate after)
echo ""
echo "--- PHASE 3 : Micro-Analyse (Graphique Escalier) ---"
taskset -c $TARGET_THREAD $PYTHON_CMD run_micro_analysis.py


echo ""
echo "=================================================="
echo "   FINISHED ! VERIFY FOLDER /results"
echo "=================================================="