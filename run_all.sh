#!/bin/bash

POD_ID=${POD_ID:-"local"}
TARGET_NODE=${TARGET_CORE:-0}

echo "=============================="
echo "POD: $POD_ID"
echo "NUMA NODE: $TARGET_NODE"
echo "=============================="

echo "--- PHASE 1 : Collecting Data ---"

# Vérifie si numactl est dispo
if command -v numactl &> /dev/null
then
    echo "[INFO] Running with NUMA binding"
    
    numactl --cpunodebind=$TARGET_NODE --membind=$TARGET_NODE \
        python3 script.py
else
    echo "[WARNING] numactl not found, fallback to taskset"
    
    taskset -c $TARGET_NODE python3 script.py
fi

echo "--- PHASE 2 : Generating plots ---"

# Moins critique → pas besoin de pinning strict
python3 run_micro_analysis_seq.py
python3 run_micro_analysis_rand.py

echo "FINISHED !"