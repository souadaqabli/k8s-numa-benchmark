#!/bin/bash
# Simplified copy of the Config A/B/C RAPL campaign script, adapted for the
# 4 matmul scenarios at N=4 only. The original script (N4-N12 scaling,
# seq/rand) is never modified.
#
# Differences from the original:
#   - No PATTERNS loop (matmul has only one mode)
#   - CORES fixed to N4 only
#   - SCENARIOS mapped directly to the matmul YAML files 
#   - Separate results file (matmul_energy_results.csv), so it never mixes
#     with the existing Config A/B/C CSVs
#   - The RAPL measurement logic itself (monitor, deltas, wraparound
#     protection) is identical to the original

set -uo pipefail
set +m

# --- ARCHITECTURE CONFIGURATION ---
K8S_MASTER="sdnuser@sdn4"
REMOTE_PATH="/home/sdnuser/k8s-numa-benchmark"

# Local RAPL counters 
PKG0="/sys/class/powercap/intel-rapl:0/energy_uj"
DRAM0="/sys/class/powercap/intel-rapl:0/intel-rapl:0:1/energy_uj"
PKG1="/sys/class/powercap/intel-rapl:1/energy_uj"
DRAM1="/sys/class/powercap/intel-rapl:1/intel-rapl:1:1/energy_uj"

MAX_PKG0=$(cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj 2>/dev/null || echo "262000000000")
MAX_PKG1=$(cat /sys/class/powercap/intel-rapl:1/max_energy_range_uj 2>/dev/null || echo "262000000000")

# --- TEST MATRIX: 4 matmul scenarios, N4 only ---
CORE="N4"

# Mapping scenario -> YAML file (path relative to $REMOTE_PATH)
declare -A SCENARIO_FILES=(
    ["baseline"]="deployments/matmul/baseline-gemv.yaml"
    ["extreme"]="deployments/matmul/extreme-gemv.yaml"
    ["cross-numa"]="deployments/matmul/cross-numa-gemv.yaml"
    ["extreme-cross"]="deployments/matmul/extreme-cross-gemv.yaml"
    ["native"]="deployments/matmul/native-gemv.yaml"
)

# Expected number of pods per scenario (baseline/cross-numa = 2 Jobs of 2 pods
# = 4 pods total ; extreme/extreme-cross = 1 Job of 4 pods)
declare -A SCENARIO_EXPECTED_PODS=(
    ["baseline"]=4
    ["extreme"]=4
    ["cross-numa"]=4
    ["extreme-cross"]=4
    ["native"]=4
)

#SCENARIOS=("baseline" "extreme" "cross-numa" "extreme-cross" "native")
SCENARIOS=("native")

RESULTS_DIR="${PWD}/results"
mkdir -p "$RESULTS_DIR/RAPL"
# Separate file, never mixed with the existing Config A/B/C CSVs
RESULTS_FILE="${RESULTS_DIR}/RAPL/matmul_gemv_energy_results.csv"

if [ ! -f "$RESULTS_FILE" ]; then
    echo "pattern,cores,scenario,duration_s,total_uj,pkg0_uj,pkg1_uj,dram0_uj,dram1_uj" > "$RESULTS_FILE"
fi

echo "========================================================"
echo " MATMUL GEMV CAMPAIGN - N4 - 4 SCENARIOS"
echo "========================================================"

for SCENARIO in "${SCENARIOS[@]}"; do

    FILE="${SCENARIO_FILES[$SCENARIO]}"
    EXPECTED_PODS="${SCENARIO_EXPECTED_PODS[$SCENARIO]}"

    echo ""
    echo ">>> TEST: Workload=matmul | Cores=${CORE} | Scenario=${SCENARIO} <<<"

    echo "[CLEANUP] Cleaning up on Master sdn4..."
    ssh ${K8S_MASTER} "kubectl delete jobs --all --wait=true 2>/dev/null" || true
    ssh ${K8S_MASTER} "kubectl delete pods --all --wait=true 2>/dev/null" || true
    sleep 5

    rm -f /tmp/rapl_results_local.txt

    # --- LOCAL RAPL MONITOR (identical to the original, runs on sdn2) ---
    echo "[INFO] Starting local RAPL monitor (5s polling)..."
    (
        last_p0=$(cat $PKG0); last_p1=$(cat $PKG1)
        last_d0=$(cat $DRAM0); last_d1=$(cat $DRAM1)

        tot_p0=0; tot_p1=0; tot_d0=0; tot_d1=0

        while true; do
            sleep 5
            cur_p0=$(cat $PKG0); cur_p1=$(cat $PKG1)
            cur_d0=$(cat $DRAM0); cur_d1=$(cat $DRAM1)

            dp0=$((cur_p0 - last_p0)); if [ $dp0 -lt 0 ]; then dp0=$((dp0 + MAX_PKG0)); fi
            dp1=$((cur_p1 - last_p1)); if [ $dp1 -lt 0 ]; then dp1=$((dp1 + MAX_PKG1)); fi
            dd0=$((cur_d0 - last_d0)); if [ $dd0 -lt 0 ]; then dd0=$((dd0 + MAX_PKG0)); fi
            dd1=$((cur_d1 - last_d1)); if [ $dd1 -lt 0 ]; then dd1=$((dd1 + MAX_PKG1)); fi

            tot_p0=$((tot_p0 + dp0)); tot_p1=$((tot_p1 + dp1))
            tot_d0=$((tot_d0 + dd0)); tot_d1=$((tot_d1 + dd1))

            last_p0=$cur_p0; last_p1=$cur_p1
            last_d0=$cur_d0; last_d1=$cur_d1

            echo "$tot_p0,$tot_p1,$tot_d0,$tot_d1" > /tmp/rapl_results_local.txt
        done
    ) &
    MONITOR_PID=$!

    # --- KUBERNETES TEST EXECUTION ---
    START_TIME=$(date +%s)

    echo "[INFO] Launching matmul job on Master sdn4..."
    ssh ${K8S_MASTER} "kubectl apply -f ${REMOTE_PATH}/${FILE}"

    echo "[INFO] Waiting for pods to be Running..."
    ELAPSED=0
    while true; do
        RUNNING=$(ssh ${K8S_MASTER} "kubectl get pods --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l")
        echo "  Running: ${RUNNING}/${EXPECTED_PODS}"
        [ "$RUNNING" -ge "$EXPECTED_PODS" ] && break
        if [ "$ELAPSED" -ge 300 ]; then
            echo "[ERROR] Timeout while waiting for pods!"
            break
        fi
        sleep 5; ELAPSED=$((ELAPSED + 5))
    done

    echo "[INFO] Waiting 60s for memory first-touch..."
    sleep 60

    echo "[INFO] Capturing numastat..."
    mkdir -p "${RESULTS_DIR}/numastat"
    {
        echo "=== NUMASTAT matmul ${CORE} ${SCENARIO} === $(date)"
        PIDS=""
        for CID in $(sudo /usr/local/bin/k3s crictl ps --state running 2>/dev/null | grep benchmark | awk '{print $1}' || true); do
            PID=$(sudo /usr/local/bin/k3s crictl inspect --output go-template --template '{{.info.pid}}' "$CID" 2>/dev/null || true)
            if echo "$PID" | grep -qE "^[0-9]+$" && [ "$PID" -gt 1 ]; then
                PIDS="$PIDS $PID"
            fi
        done

        echo "PIDs found: $(echo $PIDS | wc -w)"
        echo "PIDs: $PIDS"
        echo ""
        if [ -n "$(echo $PIDS | tr -d ' ')" ]; then
            echo "--- global numastat ---"
            sudo numastat || true
            echo ""
            echo "--- per-process numastat ---"
            sudo numastat -p $PIDS || true
            echo ""
            echo "--- numactl --hardware ---"
            numactl --hardware || true
        else
            echo "NO PID FOUND"
            sudo /usr/local/bin/k3s crictl ps --state running 2>/dev/null || true
        fi
    } > "${RESULTS_DIR}/numastat/numastat_matmul_gemv_${CORE}_${SCENARIO}.txt" 2>&1

    echo "[INFO] Waiting for pods to fully complete..."
    ssh ${K8S_MASTER} "kubectl wait --for=condition=complete job --all --timeout=7200s" || echo "[Warning] Timeout or error on wait"

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo "[INFO] Stopping local RAPL monitor..."
    kill $MONITOR_PID 2>/dev/null || true
    sleep 1

    if [ -f /tmp/rapl_results_local.txt ]; then
        RESULTS_RAW=$(cat /tmp/rapl_results_local.txt)

        PKG0_EN=$(echo $RESULTS_RAW | cut -d',' -f1)
        PKG1_EN=$(echo $RESULTS_RAW | cut -d',' -f2)
        DRAM0_EN=$(echo $RESULTS_RAW | cut -d',' -f3)
        DRAM1_EN=$(echo $RESULTS_RAW | cut -d',' -f4)

        TOTAL_EN=$((PKG0_EN + PKG1_EN + DRAM0_EN + DRAM1_EN))

        echo "[RESULT] Duration: ${DURATION}s | Total Energy: $((TOTAL_EN / 1000000)) Joules"

        echo "matmul-gemv,$CORE,$SCENARIO,$DURATION,$TOTAL_EN,$PKG0_EN,$PKG1_EN,$DRAM0_EN,$DRAM1_EN" >> "$RESULTS_FILE"
    else
        echo "[CRITICAL ERROR] The monitor could not write the results!"
    fi

    echo "--- 10s pause before the next test ---"
    sleep 10

done

echo ""
echo "========================================================"
echo " MATMUL GEMV N4 CAMPAIGN FINISHED"
echo " Results: ${RESULTS_FILE}"
echo " Numastat files: ${RESULTS_DIR}/numastat/"
echo "========================================================"