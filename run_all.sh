#!/bin/bash
# CONFIGURATION
RESULTS_DIR="results"

TARGET_THREAD=2

PYTHON_CMD="python3"

mkdir -p "$RESULTS_DIR"

echo "=================================================="
echo "   BENCHMARK COMPLET AUTOMATISÉ (Coeur #$TARGET_THREAD)"
echo "=================================================="

# 1. Topologie (Si lstopo est installé)
if command -v lstopo &> /dev/null; then
    echo "[INFO] Capture Topologie..."
    lstopo --output-format png "$RESULTS_DIR/system_topology.png" --no-io
fi

# 2. Script habituel pour capturer les metriques perf
echo ""
echo "--- PHASE 1 : Script Standard (CSV) ---"
taskset -c $TARGET_THREAD $PYTHON_CMD script.py

# 3. Le graphe Micro (Escalier)
echo ""
echo "--- PHASE 2 : Micro-Analyse (Graphique Escalier) ---"
taskset -c $TARGET_THREAD $PYTHON_CMD run_micro_analysis.py

# 4. Le graphe Macro (Latence pour lire le tableau entier en une iteration)
echo ""
echo "--- PHASE 3 : Macro-Analyse (Graphique Escalier) ---"
taskset -c $TARGET_THREAD $PYTHON_CMD run_macro_analysis.py

# 5. Le graphe Superviseur (Corrélation)
echo ""
echo "--- PHASE 4 : Analyse Scientifique (Corrélation & Misses) ---"
taskset -c $TARGET_THREAD $PYTHON_CMD run_scientific_analysis.py

# 5. Graphe pour cpu breakdown
echo ""
echo "--- PHASE 5 : plot cpu breakdown ---"
taskset -c $TARGET_THREAD $PYTHON_CMD plot_cpu_breakdown.py

echo ""
echo "=================================================="
echo "   TERMINÉ ! VÉRIFIEZ LE DOSSIER /results"
echo "=================================================="