#!/bin/bash

POD_ID=${POD_ID:-"local"}
# Découplage vital pour permettre le Cross-NUMA
CPU_NODE=${CPU_NODE:-0} 
MEM_NODE=${MEM_NODE:-0} 
OUTPUT_DIR=${OUTPUT_DIR:-"/app/results/default"}   
PATTERN=${PATTERN:-"all"}    

mkdir -p "$OUTPUT_DIR"

echo "=============================="
echo "POD:        $POD_ID"
echo "CPU NODE:   $CPU_NODE"
echo "MEM NODE:   $MEM_NODE"
echo "OUTPUT_DIR: $OUTPUT_DIR"
echo "=============================="

echo "--- PHASE 1 : Collecting Data ---"

if command -v numactl &> /dev/null; then
    echo "[INFO] Running with NUMA binding: CPU=$CPU_NODE, MEM=$MEM_NODE"
    numactl --cpunodebind=$CPU_NODE --membind=$MEM_NODE \
        python3 scripts/script_controlled.py --output-dir "$OUTPUT_DIR" --pattern "$PATTERN"
else
    echo "[WARNING] numactl not found, fallback to taskset (MEMORY BINDING WILL FAIL)"
    # taskset ne gère que le CPU, pas la RAM !
    taskset -c $CPU_NODE \
        python3 scripts/script_controlled.py --output-dir "$OUTPUT_DIR" --pattern "$PATTERN"
fi

echo "--- PHASE 2 : Generating plots ---"

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