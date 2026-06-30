#!/bin/bash
set -euo pipefail

# --- CONFIGURATION ---
REMOTE_USER="sdnuser"
REMOTE_HOST="sdn4" 
REMOTE_PATH="/home/sdnuser/k8s-numa-benchmark"

# RAPL paths
PKG0="/sys/class/powercap/intel-rapl:0/energy_uj"
DRAM0="/sys/class/powercap/intel-rapl:0/intel-rapl:0:1/energy_uj"
PKG1="/sys/class/powercap/intel-rapl:1/energy_uj"
DRAM1="/sys/class/powercap/intel-rapl:1/intel-rapl:1:1/energy_uj"

MAX_PKG0=$(cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj)
MAX_PKG1=$(cat /sys/class/powercap/intel-rapl:1/max_energy_range_uj)

# --- MATRICE DE TESTS ---
PATTERNS=("seq" "rand")
CORES=("N4" "N6" "N8" "N10" "N12")
SCENARIOS=("baseline" "extreme" "cross-numa" "extreme-cross")

# Fichier de résultats
RESULTS_DIR="${REMOTE_PATH}/results"
mkdir -p "$RESULTS_DIR/RAPL"
RESULTS_FILE="${RESULTS_DIR}/RAPL/scalability_energy_results.csv"

if [ ! -f "$RESULTS_FILE" ]; then
    echo "pattern,cores,scenario,duration_s,total_uj,pkg0_uj,pkg1_uj,dram0_uj,dram1_uj" > "$RESULTS_FILE"
fi

delta() {
    local start=$1 end=$2 max=$3
    local d=$((end - start))
    if [ $d -lt 0 ]; then d=$((d + max)); fi
    echo $d
}

echo "========================================================"
echo " REPRISE : CAMPAGNE RAND N10 (Sans la baseline)"
echo "========================================================"

for PATTERN in "${PATTERNS[@]}"; do
    BASE_DIR="deployments/scalability/${PATTERN}"
    
    for CORE in "${CORES[@]}"; do
        for SCENARIO in "${SCENARIOS[@]}"; do
            
            # =======================================================
            # FILTRE : Reprise ciblée pour rand N10
            # =======================================================
            
            # 1. On ignore tout ce qui n'est pas du pattern 'rand'
            if [ "$PATTERN" != "rand" ]; then 
                continue 
            fi

            # 2. On ignore tout ce qui n'est pas 'N10'
            if [ "$CORE" != "N10" ]; then 
                continue 
            fi

            # 3. On saute la baseline puisqu'elle est déjà terminée
            if [ "$SCENARIO" == "baseline" ]; then
                continue
            fi
            # =======================================================

            FILE="${BASE_DIR}/${CORE}/${SCENARIO}.yaml"
            echo ""
            echo ">>> TEST : Pattern=${PATTERN} | Cores=${CORE} | Scenario=${SCENARIO} <<<"
            
            echo "[CLEANUP] Nettoyage des anciens pods/jobs..."
            ssh ${REMOTE_USER}@${REMOTE_HOST} "kubectl delete jobs --all --wait=true 2>/dev/null" || true
            ssh ${REMOTE_USER}@${REMOTE_HOST} "kubectl delete pods --all --wait=true 2>/dev/null" || true
            sleep 5
            
            # Lecture Initiale RAPL
            S_PKG0=$(cat "$PKG0")
            S_DRAM0=$(cat "$DRAM0")
            S_PKG1=$(cat "$PKG1")
            S_DRAM1=$(cat "$DRAM1")
            START_TIME=$(date +%s)
            
            # Lancement de l'expérience
            echo "[INFO] Lancement de ${FILE}..."
            ssh ${REMOTE_USER}@${REMOTE_HOST} "kubectl apply -f ${REMOTE_PATH}/${FILE}"
            
            # Attente de la fin de TOUS les jobs
            echo "[INFO] Attente de la fin des pods K8s..."
            ssh ${REMOTE_USER}@${REMOTE_HOST} "kubectl wait --for=condition=complete job --all --timeout=3600s"
            
            # Lecture Finale RAPL
            END_TIME=$(date +%s)
            E_PKG0=$(cat "$PKG0")
            E_DRAM0=$(cat "$DRAM0")
            E_PKG1=$(cat "$PKG1")
            E_DRAM1=$(cat "$DRAM1")
            
            # Calculs
            PKG0_EN=$(delta  $S_PKG0  $E_PKG0  $MAX_PKG0)
            PKG1_EN=$(delta  $S_PKG1  $E_PKG1  $MAX_PKG1)
            DRAM0_EN=$(delta $S_DRAM0 $E_DRAM0 $MAX_PKG0)
            DRAM1_EN=$(delta $S_DRAM1 $E_DRAM1 $MAX_PKG1)
            TOTAL_EN=$((PKG0_EN + PKG1_EN))
            DURATION=$((END_TIME - START_TIME))
            
            echo "[RESULT] Durée : ${DURATION}s | Énergie : $(echo "scale=1; $TOTAL_EN / 1000000" | bc) Joules"
            
            # Sauvegarde
            echo "$PATTERN,$CORE,$SCENARIO,$DURATION,$TOTAL_EN,$PKG0_EN,$PKG1_EN,$DRAM0_EN,$DRAM1_EN" >> "$RESULTS_FILE"
            
        done
    done
done

echo ""
echo "========================================================"
echo " FIN DE LA REPRISE : TESTS RAND N10 AJOUTÉS"
echo "Résultats ajoutés dans : $RESULTS_FILE"
echo "========================================================"