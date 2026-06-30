#!/bin/bash

POD_ID=${POD_ID:-"local"}
OUTPUT_DIR=${OUTPUT_DIR:-"/app/results/default"}   
PATTERN=${PATTERN:-"all"}    

# --- Variables NUMA ---
MEM_NODE=${MEM_NODE:-0} 

# L'interrupteur magique : "node" (ancien) ou "core" (nouveau)
BINDING_MODE=${BINDING_MODE:-"node"} 

# Variables selon le mode
CPU_NODE=${CPU_NODE:-0}              # Utilisé si BINDING_MODE="node"
PHYS_CPU_LIST=${PHYS_CPU_LIST:-"0"}  # Utilisé si BINDING_MODE="core"

mkdir -p "$OUTPUT_DIR"

echo "=============================="
echo "POD:        $POD_ID"
echo "MODE:       $BINDING_MODE"
echo "MEM NODE:   $MEM_NODE"
echo "OUTPUT_DIR: $OUTPUT_DIR"
echo "=============================="

echo "--- PHASE 1 : Collecting Data ---"

if command -v numactl &> /dev/null; then
    if [ "$BINDING_MODE" == "core" ]; then
        echo "[INFO] NOUVEAU MODE (Chirurgical) : CPUs=$PHYS_CPU_LIST, MEM=$MEM_NODE"
        numactl --physcpubind=$PHYS_CPU_LIST --membind=$MEM_NODE \
            python3 scripts/script_controlled.py --output-dir "$OUTPUT_DIR" --pattern "$PATTERN"
    else
        echo "[INFO] ANCIEN MODE (Nœud Global) : CPU_NODE=$CPU_NODE, MEM=$MEM_NODE"
        numactl --cpunodebind=$CPU_NODE --membind=$MEM_NODE \
            python3 scripts/script_controlled.py --output-dir "$OUTPUT_DIR" --pattern "$PATTERN"
    fi
else
    echo "[WARNING] numactl not found, fallback to taskset"
    if [ "$BINDING_MODE" == "core" ]; then
        taskset -c $PHYS_CPU_LIST python3 scripts/script_controlled.py --output-dir "$OUTPUT_DIR" --pattern "$PATTERN"
    else
        taskset -c $CPU_NODE python3 scripts/script_controlled.py --output-dir "$OUTPUT_DIR" --pattern "$PATTERN"
    fi
fi

echo "FINISHED !"
#echo "--- PHASE 2 : Generating plots ---"

#if [ "$PATTERN" == "sequential" ]; then
    #echo "[INFO] Generating Sequential plots..."
    #python3 scripts/run_micro_analysis_seq.py "$OUTPUT_DIR"

#elif [ "$PATTERN" == "random" ]; then
    #echo "[INFO] Generating Random plots..."
    #python3 scripts/run_micro_analysis_rand.py "$OUTPUT_DIR"

#else
    #echo "[INFO] Generating All plots..."
    #python3 scripts/run_micro_analysis_seq.py "$OUTPUT_DIR"
    #python3 scripts/run_micro_analysis_rand.py "$OUTPUT_DIR"
#fi

echo "FINISHED !"