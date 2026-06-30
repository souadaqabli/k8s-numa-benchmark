#!/bin/bash
# =============================================================================
# run_overload_campaign.sh
# À lancer sur sdn2.
#
# Ce script orchestre le test de surcharge NUMA en 3 couches simultanées :
#   1. Mesure RAPL  (énergie PKG + DRAM en polling 5s)
#   2. Surveillance NUMA (numastat + affinité CPU toutes les 30s)
#   3. Exécution K8s (apply yaml → wait completion)
#
# Usage :
#   bash scripts/host/run_overload_campaign.sh [N16|N24] [seq|rand|both] [runs]
#
# Exemples :
#   bash scripts/host/run_overload_campaign.sh N16 both 3
#   bash scripts/host/run_overload_campaign.sh N24 seq 1
# =============================================================================
set -uo pipefail   # PAS de -e : les erreurs de monitoring ne tuent pas le script
set +m

# --- PARAMÈTRES ---
N_PODS="${1:-N16}"        # N16 ou N24
PATTERN_ARG="${2:-both}"  # seq, rand, ou both
N_RUNS="${3:-3}"          # nombre de répétitions pour médiane robuste

K8S_MASTER="sdnuser@sdn4"
REMOTE_PATH="/home/sdnuser/k8s-numa-benchmark"

# --- RAPL ---
PKG0="/sys/class/powercap/intel-rapl:0/energy_uj"
DRAM0="/sys/class/powercap/intel-rapl:0/intel-rapl:0:1/energy_uj"
PKG1="/sys/class/powercap/intel-rapl:1/energy_uj"
DRAM1="/sys/class/powercap/intel-rapl:1/intel-rapl:1:1/energy_uj"
MAX_PKG0=$(cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj)
MAX_PKG1=$(cat /sys/class/powercap/intel-rapl:1/max_energy_range_uj)

# --- SORTIES ---
RESULTS_DIR="${REMOTE_PATH}/results"
RAPL_FILE="${RESULTS_DIR}/RAPL/overload_energy_results.csv"
NUMA_DIR="${RESULTS_DIR}/numa_monitoring"

mkdir -p "${RESULTS_DIR}/RAPL" "$NUMA_DIR"

[ ! -f "$RAPL_FILE" ] && \
    echo "pattern,cores,scenario,run,duration_s,total_uj,pkg0_uj,pkg1_uj,dram0_uj,dram1_uj" \
    > "$RAPL_FILE"

# =============================================================================
# UTILITAIRES
# =============================================================================

delta() {
    local start=$1 end=$2 max=$3
    local d=$((end - start))
    [ $d -lt 0 ] && d=$((d + max))
    echo $d
}

# Récupère les PIDs des containers du job en cours sur sdn2
get_benchmark_pids() {
    local label=$1
    local pids=""
    for cid in $(sudo /usr/local/bin/k3s crictl ps 2>/dev/null \
                 | grep "$label" | awk '{print $1}'); do
        pid=$(sudo /usr/local/bin/k3s crictl inspect \
              --output go-template --template '{{.info.pid}}' \
              "$cid" 2>/dev/null)
        if echo "$pid" | grep -qE '^[0-9]+$' && [ "$pid" -gt 1 ]; then
            pids="$pids $pid"
        fi
    done
    echo "$pids"
}

# =============================================================================
# SURVEILLANCE NUMA : capture un instantané complet
# =============================================================================
capture_numa_snapshot() {
    local label=$1   # ex: overload-n16-seq
    local tag=$2     # ex: T0_start, T1_mid, T2_end
    local run=$3     # numéro du run
    local outdir="${NUMA_DIR}/${label}/run${run}"
    mkdir -p "$outdir"

    PIDS=$(get_benchmark_pids "$label" 2>/dev/null || true)
    if [ -z "$PIDS" ]; then
        echo "  [NUMA] Aucun PID trouvé pour $label à $tag"
        return 0
    fi

    echo "  [NUMA] Capture $tag — PIDs :$PIDS"

    # Toute la capture est dans un sous-shell isolé.
    # Une erreur ici (numastat absent, sudo KO, etc.) n'arrête PAS le script principal.
    (
        set +e   # Les erreurs de monitoring sont non-fatales

        # 1. Stats système NUMA globales (si numastat disponible)
        if command -v numastat &>/dev/null; then
            sudo numastat         > "${outdir}/numastat_system_${tag}.txt" 2>&1 || true
            sudo numastat -m      > "${outdir}/numastat_mem_${tag}.txt"    2>&1 || true
            sudo numastat -p $PIDS > "${outdir}/numastat_pids_${tag}.txt"  2>&1 || true
        else
            echo "numastat non disponible" > "${outdir}/numastat_system_${tag}.txt"
        fi

        # 2. Affinité CPU par processus (quel socket ?)
        {
            echo "=== Affinité CPU — $tag ==="
            for pid in $PIDS; do
                cpus=$(grep "Cpus_allowed_list:" /proc/$pid/status 2>/dev/null | awk '{print $2}')
                echo "PID $pid : CPUs_allowed=$cpus"
            done
        } > "${outdir}/cpu_affinity_${tag}.txt" 2>&1 || true

        # 3. Cartes mémoire NUMA par processus (où sont allouées les pages ?)
        {
            echo "=== NUMA Maps — $tag ==="
            for pid in $PIDS; do
                echo "--- PID $pid ---"
                sudo cat /proc/$pid/numa_maps 2>/dev/null \
                    | grep -E "anon|heap" \
                    | awk '$0 ~ /N[0-9]+=/ {print}' \
                    | head -8 || true
            done
        } > "${outdir}/numa_maps_${tag}.txt" 2>&1 || true

        # 4. Perf events NUMA (LOCAL_DRAM vs REMOTE_DRAM)
        #    → REMOTE_DRAM > 0 = preuve directe de cross-NUMA
        {
            FIRST_PID=$(echo $PIDS | awk '{print $1}')
            if perf list 2>/dev/null | grep -q "MEM_LOAD_L3_MISS"; then
                echo "=== Perf NUMA Events — $tag (10s) ==="
                sudo perf stat \
                    -e MEM_LOAD_L3_MISS_RETIRED.LOCAL_DRAM \
                    -e MEM_LOAD_L3_MISS_RETIRED.REMOTE_DRAM \
                    -p "$FIRST_PID" -- sleep 10 2>&1 \
                    | grep -E "LOCAL_DRAM|REMOTE_DRAM|not counted" || true
            else
                echo "perf NUMA events non disponibles sur ce kernel"
            fi
        } > "${outdir}/perf_numa_${tag}.txt" 2>&1 || true

    ) || true   # le sous-shell peut échouer sans conséquence

    echo "  [NUMA] Sauvegardé dans : $outdir/*_${tag}.txt"
}

# =============================================================================
# FONCTION PRINCIPALE : 1 run complet
# =============================================================================
run_overload_once() {
    local pattern=$1  # seq ou rand
    local n_pods=$2   # N16 ou N24
    local run_id=$3
    local n_pods_lower="${n_pods,,}"
    local job_name="overload-${n_pods_lower}-${pattern}"
    local yaml_file="${REMOTE_PATH}/deployments/overload/${n_pods}/${pattern}.yaml"

    echo ""
    echo "========================================================"
    echo " RUN $run_id | Pattern=$pattern | Pods=$n_pods"
    echo " Job: $job_name"
    echo "========================================================"

    # --- Nettoyage ---
    echo "[1/6] Nettoyage K8s..."
    ssh ${K8S_MASTER} "kubectl delete jobs --all --wait=true 2>/dev/null || true"
    ssh ${K8S_MASTER} "kubectl delete pods --all --wait=true 2>/dev/null || true"
    sleep 5
    rm -f /tmp/rapl_overload_tmp.txt

    # --- Snapshot NUMA avant le job (état de référence) ---
    mkdir -p "${NUMA_DIR}/${job_name}/run${run_id}"
    sudo numastat > "${NUMA_DIR}/${job_name}/run${run_id}/numastat_system_T_BEFORE.txt" 2>&1
    sudo numastat -m > "${NUMA_DIR}/${job_name}/run${run_id}/numastat_mem_T_BEFORE.txt" 2>&1
    echo "[2/6] Snapshot NUMA baseline enregistré (avant le job)"

    # --- Lancer le moniteur RAPL en arrière-plan ---
    echo "[3/6] Démarrage moniteur RAPL..."
    (
        last_p0=$(cat $PKG0); last_p1=$(cat $PKG1)
        last_d0=$(cat $DRAM0); last_d1=$(cat $DRAM1)
        tot_p0=0; tot_p1=0; tot_d0=0; tot_d1=0

        while true; do
            sleep 5
            cur_p0=$(cat $PKG0); cur_p1=$(cat $PKG1)
            cur_d0=$(cat $DRAM0); cur_d1=$(cat $DRAM1)

            dp0=$(delta $last_p0 $cur_p0 $MAX_PKG0)
            dp1=$(delta $last_p1 $cur_p1 $MAX_PKG1)
            dd0=$(delta $last_d0 $cur_d0 $MAX_PKG0)
            dd1=$(delta $last_d1 $cur_d1 $MAX_PKG1)

            tot_p0=$((tot_p0 + dp0)); tot_p1=$((tot_p1 + dp1))
            tot_d0=$((tot_d0 + dd0)); tot_d1=$((tot_d1 + dd1))

            last_p0=$cur_p0; last_p1=$cur_p1
            last_d0=$cur_d0; last_d1=$cur_d1

            echo "$tot_p0,$tot_p1,$tot_d0,$tot_d1" > /tmp/rapl_overload_tmp.txt
        done
    ) &
    RAPL_PID=$!

    # --- Lancer le job K8s ---
    echo "[4/6] Lancement du job K8s..."
    START_TIME=$(date +%s)
    ssh ${K8S_MASTER} "kubectl apply -f ${yaml_file}"

    # --- Surveillance NUMA pendant l'exécution ---
    echo "[5/6] Surveillance NUMA en cours..."

    # T0 : 20s après le lancement (pods démarrés, buffers alloués)
    sleep 20
    capture_numa_snapshot "$job_name" "T0_start" "$run_id"

    # T1 : mi-parcours (~60s après start)
    sleep 40
    capture_numa_snapshot "$job_name" "T1_mid" "$run_id"

    # T2 : vers la fin (si le job est long, sinon on attend la fin)
    sleep 60
    capture_numa_snapshot "$job_name" "T2_late" "$run_id"

    # --- Attendre la fin complète ---
    echo "[5/6] Attente fin du job (timeout 2h)..."
    ssh ${K8S_MASTER} "kubectl wait --for=condition=complete job --all --timeout=7200s" \
        || ssh ${K8S_MASTER} "kubectl wait --for=condition=failed job --all --timeout=10s" \
        || echo "[WARN] kubectl wait terminé (job complet ou timeout)"
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    # T_END : snapshot final
    capture_numa_snapshot "$job_name" "T3_end" "$run_id"

    # --- Arrêter le moniteur RAPL ---
    kill $RAPL_PID 2>/dev/null || true
    sleep 1

    # --- Enregistrer les résultats ---
    if [ -f /tmp/rapl_overload_tmp.txt ]; then
        RAW=$(cat /tmp/rapl_overload_tmp.txt)
        P0=$(echo $RAW | cut -d',' -f1)
        P1=$(echo $RAW | cut -d',' -f2)
        D0=$(echo $RAW | cut -d',' -f3)
        D1=$(echo $RAW | cut -d',' -f4)
        TOTAL=$((P0 + P1 + D0 + D1))

        echo "[RESULT] Durée=${DURATION}s | PKG0=$((P0/1000000))J | PKG1=$((P1/1000000))J | DRAM0=$((D0/1000000))J | DRAM1=$((D1/1000000))J | Total=$((TOTAL/1000000))J"
        echo "$pattern,$n_pods,overload,$run_id,$DURATION,$TOTAL,$P0,$P1,$D0,$D1" \
             >> "$RAPL_FILE"
        echo "[6/6] Résultats sauvegardés dans $RAPL_FILE"
    else
        echo "[ERREUR] Le moniteur RAPL n'a pas écrit de données !"
    fi
}

# =============================================================================
# LECTURE DU NUMASTAT POUR AFFICHER LES PREUVES IMMÉDIATEMENT
# =============================================================================
print_numa_summary() {
    local job_name=$1
    local run_id=$2
    local outdir="${NUMA_DIR}/${job_name}/run${run_id}"

    echo ""
    echo "============================================================"
    echo " RÉSUMÉ PREUVES NUMA — $job_name run $run_id"
    echo "============================================================"

    # Comparer numa_hit vs numa_miss entre T_BEFORE et T3_end
    for tag in "T_BEFORE" "T0_start" "T1_mid" "T3_end"; do
        f="${outdir}/numastat_system_${tag}.txt"
        if [ -f "$f" ]; then
            echo ""
            echo "--- $tag ---"
            grep -E "numa_hit|numa_miss|numa_local|numa_foreign|numa_other" "$f" 2>/dev/null \
                || grep -v "^$" "$f" | head -6
        fi
    done

    echo ""
    echo "--- CPU Affinity (T0_start) ---"
    cat "${outdir}/cpu_affinity_T0_start.txt" 2>/dev/null || echo "Fichier manquant"

    echo ""
    echo "--- Perf NUMA Events (T1_mid) ---"
    cat "${outdir}/perf_numa_T1_mid.txt" 2>/dev/null || echo "Fichier manquant"
}

# =============================================================================
# BOUCLE PRINCIPALE
# =============================================================================
if [ "$PATTERN_ARG" = "both" ]; then
    PATTERNS=("seq" "rand")
else
    PATTERNS=("$PATTERN_ARG")
fi

echo "=== CAMPAGNE OVERLOAD : $N_PODS | Patterns=${PATTERNS[*]} | Runs=$N_RUNS ==="
echo "=== Fichier résultats : $RAPL_FILE ==="
echo "=== Répertoire NUMA   : $NUMA_DIR ==="

for PATTERN in "${PATTERNS[@]}"; do
    for RUN in $(seq 1 $N_RUNS); do
        run_overload_once "$PATTERN" "$N_PODS" "$RUN"
        print_numa_summary "overload-${N_PODS,,}-${PATTERN}" "$RUN"
        echo ""
        echo "--- Pause 10s entre les runs ---"
        sleep 10
    done
done

echo ""
echo "=== CAMPAGNE TERMINÉE ==="
echo "Résultats RAPL    : $RAPL_FILE"
echo "Données NUMA      : $NUMA_DIR"
echo ""
echo "Prochaine étape → extraire les instructions :"
echo "  python3 analysis/tables/extract_instructions_scalability.py"
echo "Puis calculer nJ/inst :"
echo "  python3 analysis/energy/generate_plots_rapl_instructions_scale.py"
