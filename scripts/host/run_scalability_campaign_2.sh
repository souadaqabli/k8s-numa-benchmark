#!/bin/bash
set -euo pipefail
set +m # Désactive l'affichage du bloc "Terminated"

# --- CONFIGURATION ARCHITECTURE ---
K8S_MASTER="sdnuser@sdn4"
REMOTE_PATH="/home/sdnuser/k8s-numa-benchmark"

# Les compteurs RAPL Locaux
PKG0="/sys/class/powercap/intel-rapl:0/energy_uj"
DRAM0="/sys/class/powercap/intel-rapl:0/intel-rapl:0:1/energy_uj"
PKG1="/sys/class/powercap/intel-rapl:1/energy_uj"
DRAM1="/sys/class/powercap/intel-rapl:1/intel-rapl:1:1/energy_uj"

# Lecture locale des plafonds RAPL sur sdn2
MAX_PKG0=$(cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj)
MAX_PKG1=$(cat /sys/class/powercap/intel-rapl:1/max_energy_range_uj)

# --- MATRICE DE TESTS ---
PATTERNS=("rand")
CORES=("N12")
# MODIFICATION ICI : On cible uniquement les deux derniers scénarios restants
SCENARIOS=("cross-numa" "extreme-cross")

# Fichier de résultats
RESULTS_DIR="${PWD}/results"
mkdir -p "$RESULTS_DIR/RAPL"
# Il écrira directement à la fin de ton fichier final
RESULTS_FILE="${RESULTS_DIR}/RAPL/scalability_energy_results.csv"

if [ ! -f "$RESULTS_FILE" ]; then
    echo "pattern,cores,scenario,duration_s,total_uj,pkg0_uj,pkg1_uj,dram0_uj,dram1_uj" > "$RESULTS_FILE"
fi

echo "========================================================"
echo " DERNIÈRE LIGNE DROITE : N12 cross-numa et extreme-cross"
echo "========================================================"

for PATTERN in "${PATTERNS[@]}"; do
    BASE_DIR="deployments/scalability/${PATTERN}"
    
    for CORE in "${CORES[@]}"; do
        for SCENARIO in "${SCENARIOS[@]}"; do
            
            FILE="${BASE_DIR}/${CORE}/${SCENARIO}.yaml"
            echo ""
            echo ">>> TEST : Pattern=${PATTERN} | Cores=${CORE} | Scenario=${SCENARIO} <<<"
            
            echo "[CLEANUP] Nettoyage sur le Master sdn4..."
            ssh ${K8S_MASTER} "kubectl delete jobs --all --wait=true 2>/dev/null" || true
            ssh ${K8S_MASTER} "kubectl delete pods --all --wait=true 2>/dev/null" || true
            sleep 5
            
            # --- SÉCURITÉ ---
            # On supprime le vieux fichier temporaire pour forcer de nouvelles valeurs
            rm -f /tmp/rapl_results_local.txt
            
            # --- LE MONITEUR RAPL LOCAL (Tourne sur sdn2) ---
            echo "[INFO] Lancement du moniteur RAPL local (Polling 5s)..."
            (
                last_p0=$(cat $PKG0); last_p1=$(cat $PKG1)
                last_d0=$(cat $DRAM0); last_d1=$(cat $DRAM1)
                
                tot_p0=0; tot_p1=0; tot_d0=0; tot_d1=0
                
                while true; do
                    sleep 5
                    cur_p0=$(cat $PKG0); cur_p1=$(cat $PKG1)
                    cur_d0=$(cat $DRAM0); cur_d1=$(cat $DRAM1)
                    
                    # Deltas avec protection
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
            
            # --- EXÉCUTION DU TEST KUBERNETES ---
            START_TIME=$(date +%s)
            
            echo "[INFO] Lancement à neuf du job K8s sur le Master sdn4..."
            ssh ${K8S_MASTER} "kubectl apply -f ${REMOTE_PATH}/${FILE}"
            
            echo "[INFO] Attente de la fin des pods..."
            ssh ${K8S_MASTER} "kubectl wait --for=condition=complete job --all --timeout=7200s"
            
            END_TIME=$(date +%s)
            DURATION=$((END_TIME - START_TIME))
            
            # --- ARRÊT ET COLLECTE ---
            echo "[INFO] Arrêt du moniteur RAPL local..."
            kill $MONITOR_PID 2>/dev/null || true
            sleep 1 
            
            # On vérifie que le moniteur a bien créé les nouvelles données
            if [ -f /tmp/rapl_results_local.txt ]; then
                RESULTS_RAW=$(cat /tmp/rapl_results_local.txt)
                
                PKG0_EN=$(echo $RESULTS_RAW | cut -d',' -f1)
                PKG1_EN=$(echo $RESULTS_RAW | cut -d',' -f2)
                DRAM0_EN=$(echo $RESULTS_RAW | cut -d',' -f3)
                DRAM1_EN=$(echo $RESULTS_RAW | cut -d',' -f4)
                TOTAL_EN=$((PKG0_EN + PKG1_EN))
                
                echo "[RESULT] Durée : ${DURATION}s | Énergie Totale : $((TOTAL_EN / 1000000)) Joules"
                
                # Sauvegarde locale
                echo "$PATTERN,$CORE,$SCENARIO,$DURATION,$TOTAL_EN,$PKG0_EN,$PKG1_EN,$DRAM0_EN,$DRAM1_EN" >> "$RESULTS_FILE"
            else
                echo "[ERREUR CRITIQUE] Le moniteur n'a pas pu écrire les résultats !"
            fi
            
        done
    done
done

echo ""
echo "========================================================"
echo " FIN TOTALE DE LA CAMPAGNE"
echo "========================================================"