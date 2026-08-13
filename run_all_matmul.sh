#!/bin/bash
# Calls script_controlled_matmul.py instead of
# script_controlled.py. 

POD_ID=${POD_ID:-"local"}
OUTPUT_DIR=${OUTPUT_DIR:-"/app/results/default"}

MEM_NODE=${MEM_NODE:-0}
BINDING_MODE=${BINDING_MODE:-"node"}
CPU_NODE=${CPU_NODE:-0}
PHYS_CPU_LIST=${PHYS_CPU_LIST:-"0"}

mkdir -p "$OUTPUT_DIR"

echo "=============================="
echo "POD:        $POD_ID"
echo "MODE:       $BINDING_MODE"
echo "MEM NODE:   $MEM_NODE"
echo "OUTPUT_DIR: $OUTPUT_DIR"
echo "WORKLOAD:   matmul"
echo "=============================="

echo "--- PHASE 1 : Collecting Data (matmul) ---"

if command -v numactl &> /dev/null; then
    if [ "$BINDING_MODE" == "core" ]; then
        echo "[INFO] NEW MODE (Surgical) : CPUs=$PHYS_CPU_LIST, MEM=$MEM_NODE"
        numactl --physcpubind=$PHYS_CPU_LIST --membind=$MEM_NODE \
            python3 scripts/script_controlled_matmul.py --output-dir "$OUTPUT_DIR"
    else
        echo "[INFO] OLD MODE (Global Node) : CPU_NODE=$CPU_NODE, MEM=$MEM_NODE"
        numactl --cpunodebind=$CPU_NODE --membind=$MEM_NODE \
            python3 scripts/script_controlled_matmul.py --output-dir "$OUTPUT_DIR"
    fi
else
    echo "[WARNING] numactl not found, fallback to taskset"
    if [ "$BINDING_MODE" == "core" ]; then
        taskset -c $PHYS_CPU_LIST python3 scripts/script_controlled_matmul.py --output-dir "$OUTPUT_DIR"
    else
        taskset -c $CPU_NODE python3 scripts/script_controlled_matmul.py --output-dir "$OUTPUT_DIR"
    fi
fi

echo "FINISHED !"