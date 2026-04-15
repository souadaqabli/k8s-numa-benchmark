#!/bin/bash

POD_ID=${POD_ID:-"local"}
TARGET_NODE=${TARGET_NODE:-0}                          
OUTPUT_DIR=${OUTPUT_DIR:-"/app/results/default"}       

mkdir -p "$OUTPUT_DIR"

echo "=============================="
echo "POD:        $POD_ID"
echo "NUMA NODE:  $TARGET_NODE"
echo "OUTPUT_DIR: $OUTPUT_DIR"
echo "=============================="

echo "--- PHASE 1 : Collecting Data ---"

if command -v numactl &> /dev/null; then
    echo "[INFO] Running with NUMA binding on node $TARGET_NODE"
    numactl --cpunodebind=$TARGET_NODE --membind=$TARGET_NODE \
        python3 script.py --output-dir "$OUTPUT_DIR"
else
    echo "[WARNING] numactl not found, fallback to taskset"
    taskset -c $TARGET_NODE \
        python3 script.py --output-dir "$OUTPUT_DIR"
fi

echo "--- PHASE 2 : Generating plots ---"

# Ces scripts lisent les CSV produits par script.py
# Ils doivent savoir où lire ET où écrire
python3 run_micro_analysis_seq.py --output-dir "$OUTPUT_DIR"
python3 run_micro_analysis_rand.py --output-dir "$OUTPUT_DIR"

echo "FINISHED !"