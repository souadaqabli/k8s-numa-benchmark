#!/bin/bash
set -e

# ============================================================
# REDIS NUMA BENCHMARK — HOSTPATH VERSION (OPEN-SUSE FIX)
# ============================================================

NAMESPACE="default"
SCENARIOS=("baseline" "extreme" "cross" "extreme-cross")
RESULTS_DIR="$HOME/k8s-numa-benchmark/results/redis"
WORKER_NODE="sdn2"
BENCHMARK_DURATION_SEC=30
MAX_RETRIES=5
RETRY_DELAY=10
REDIS_IMAGE="redis:7"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_err()   { echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"; }

# ============================================================
# DETECT NUMACTL PATHS (FIXED FOR OPEN-SUSE /usr/lib64)
# ============================================================
NUMACTL_BIN=""
NUMACTL_LIB=""

detect_numactl_paths() {
    log_info "Detecting numactl paths on $WORKER_NODE..."
    
    NUMACTL_BIN=$(ssh "$WORKER_NODE" "which numactl" 2>/dev/null || true)
    if [[ -z "$NUMACTL_BIN" ]]; then
        log_err "numactl not found on $WORKER_NODE. Install: sudo zypper install numactl"
        exit 1
    fi
    log_ok "numactl binary: $NUMACTL_BIN"
    
    # Try ldd first
    NUMACTL_LIB=$(ssh "$WORKER_NODE" "ldd $NUMACTL_BIN 2>/dev/null | grep libnuma | awk '{print \$3}'" || true)
    
    # If ldd fails or returns "not found", search common paths including /usr/lib64
    if [[ -z "$NUMACTL_LIB" || "$NUMACTL_LIB" == "not" || ! "$NUMACTL_LIB" =~ ^/ ]]; then
        NUMACTL_LIB=$(ssh "$WORKER_NODE" "find /lib /usr/lib /lib64 /usr/lib64 -name 'libnuma.so.1' 2>/dev/null | head -1" || true)
    fi
    
    if [[ -z "$NUMACTL_LIB" || ! "$NUMACTL_LIB" =~ ^/ ]]; then
        log_err "libnuma.so.1 not found on $WORKER_NODE. Install: sudo zypper install libnuma1"
        exit 1
    fi
    log_ok "numactl library: $NUMACTL_LIB"
}

# ============================================================
# PREREQUISITES
# ============================================================
check_prerequisites() {
    log_info "=== Checking prerequisites ==="
    if ! ssh -o ConnectTimeout=5 "$WORKER_NODE" "echo OK" > /dev/null 2>&1; then
        log_err "SSH to $WORKER_NODE failed"; exit 1
    fi
    log_ok "SSH to $WORKER_NODE: OK"
    
    if ! ssh "$WORKER_NODE" "test -f /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"; then
        log_err "RAPL not accessible"; exit 1
    fi
    log_ok "RAPL accessible"
    
    if ! ssh "$WORKER_NODE" "which perf" > /dev/null 2>&1; then
        log_warn "perf not found, installing..."
        ssh "$WORKER_NODE" "sudo apt-get install -y linux-tools-generic linux-tools-common"
    fi
    log_ok "perf available"
    
    mkdir -p "$RESULTS_DIR"
    log_ok "Results folder: $RESULTS_DIR"
    
    log_info "Cleaning up existing Redis pods..."
    for s in "${SCENARIOS[@]}"; do
        kubectl delete pod "redis-$s" --grace-period=0 --force 2>/dev/null || true
    done
    kubectl delete pod redis-bench --grace-period=0 --force 2>/dev/null || true
    sleep 3
    log_ok "Cleanup complete"
    
    detect_numactl_paths
}

# ============================================================
# RAPL
# ============================================================
RAPL_WRAPAROUND_LIMIT=4294967296

measure_rapl() {
    local f=$1 p=$2
    log_info "Reading RAPL on $WORKER_NODE ($p)..."
    local pkg0=$(ssh "$WORKER_NODE" "cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj")
    local pkg1=$(ssh "$WORKER_NODE" "cat /sys/class/powercap/intel-rapl/intel-rapl:1/energy_uj")
    local dram0=$(ssh "$WORKER_NODE" "cat /sys/class/powercap/intel-rapl/intel-rapl:0:0/energy_uj 2>/dev/null || echo 0")
    local dram1=$(ssh "$WORKER_NODE" "cat /sys/class/powercap/intel-rapl/intel-rapl:1:0/energy_uj 2>/dev/null || echo 0")
    echo "$pkg0,$pkg1,$dram0,$dram1" > "$f"
    log_ok "RAPL $p: pkg0=$pkg0 pkg1=$pkg1 dram0=$dram0 dram1=$dram1"
}

calc_energy() {
    local b=$1 a=$2
    local bp0 bp1 bd0 bd1; IFS=',' read -r bp0 bp1 bd0 bd1 < "$b"
    local ap0 ap1 ad0 ad1; IFS=',' read -r ap0 ap1 ad0 ad1 < "$a"
    local d0=$((ap0-bp0)); [[ $d0 -lt 0 ]] && d0=$((d0+RAPL_WRAPAROUND_LIMIT))
    local d1=$((ap1-bp1)); [[ $d1 -lt 0 ]] && d1=$((d1+RAPL_WRAPAROUND_LIMIT))
    local d2=$((ad0-bd0)); [[ $d2 -lt 0 ]] && d2=$((d2+RAPL_WRAPAROUND_LIMIT))
    local d3=$((ad1-bd1)); [[ $d3 -lt 0 ]] && d3=$((d3+RAPL_WRAPAROUND_LIMIT))
    local total_uj=$((d0+d1+d2+d3))
    echo "scale=6; $total_uj/1000000" | bc
    local detail="${b/_rapl_before.csv/_rapl_detail.csv}"
    { echo "domain,before_uj,after_uj,delta_uj"
      echo "pkg0,$bp0,$ap0,$d0"; echo "pkg1,$bp1,$ap1,$d1"
      echo "dram0,$bd0,$ad0,$d2"; echo "dram1,$bd1,$ad1,$d3"
      echo "total,,$total_uj,$(echo "scale=6; $total_uj/1000000" | bc)"
    } > "$detail"
}

# ============================================================
# WAIT FOR REDIS
# ============================================================
wait_for_redis() {
    local pod=$1 r=0
    log_info "Waiting for $pod to start..."
    while true; do
        local phase=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null)
        [[ "$phase" == "Running" ]] && break
        [[ "$phase" == "Failed" || "$phase" == "Error" ]] && { log_err "Pod in $phase"; kubectl logs "$pod" 2>/dev/null; return 1; }
        r=$((r+1)); [[ $r -ge $MAX_RETRIES ]] && { log_err "Timeout waiting for Running"; return 1; }
        log_warn "Attempt $r/$MAX_RETRIES - phase: ${phase:-Unknown}, waiting ${RETRY_DELAY}s..."
        sleep "$RETRY_DELAY"
    done
    r=0
    while true; do
        local cstate=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null)
        [[ -n "$cstate" ]] && { log_err "Container waiting: $cstate"; kubectl logs "$pod" --tail=20 2>/dev/null; return 1; }
        kubectl exec -n "$NAMESPACE" "$pod" -- redis-cli ping 2>/dev/null | grep -q "PONG" && { log_ok "$pod responds (PONG)"; return 0; }
        r=$((r+1)); [[ $r -ge $MAX_RETRIES ]] && { log_err "No PONG after $MAX_RETRIES"; kubectl logs "$pod" --tail=20 2>/dev/null; return 1; }
        log_warn "Ping attempt $r/$MAX_RETRIES - waiting ${RETRY_DELAY}s..."
        sleep "$RETRY_DELAY"
    done
}

# ============================================================
# CLEANUP
# ============================================================
cleanup() {
    log_warn "Emergency cleanup..."
    for s in "${SCENARIOS[@]}"; do kubectl delete pod "redis-$s" --grace-period=0 --force 2>/dev/null || true; done
    kubectl delete pod redis-bench --grace-period=0 --force 2>/dev/null || true
    ssh "$WORKER_NODE" "sudo pkill -f 'perf stat'" 2>/dev/null || true
    log_info "Cleanup done"
}
trap cleanup EXIT INT TERM

# ============================================================
# BUILD MANIFEST WITH HOSTPATH
# ============================================================
build_manifest() {
    local scenario=$1 pod="redis-$scenario" cmd
    
    case "$scenario" in
        baseline)      cmd="numactl --physcpubind=0,2 --membind=0 redis-server --protected-mode no" ;;
        extreme)       cmd="numactl --physcpubind=0,2,4,6 --membind=0 redis-server --protected-mode no" ;;
        cross)         cmd="numactl --physcpubind=0,2 --membind=1 redis-server --protected-mode no" ;;
        extreme-cross) cmd="numactl --physcpubind=0,2,4,6 --membind=1 redis-server --protected-mode no" ;;
        *) log_err "Unknown scenario"; exit 1 ;;
    esac

    cat <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: $pod
  labels:
    app: redis
    topology: $scenario
spec:
  nodeName: $WORKER_NODE
  containers:
  - name: redis
    image: $REDIS_IMAGE
    imagePullPolicy: IfNotPresent
    command: ["/bin/sh", "-c"]
    args:
      - $cmd
    ports:
    - containerPort: 6379
    resources:
      limits:
        memory: "4Gi"
      requests:
        cpu: "2"
        memory: "4Gi"
    securityContext:
      privileged: true
      runAsUser: 0
    volumeMounts:
    - name: numactl-bin
      mountPath: /usr/bin/numactl
    - name: numactl-lib
      mountPath: /usr/lib/x86_64-linux-gnu/libnuma.so.1
  volumes:
  - name: numactl-bin
    hostPath:
      path: $NUMACTL_BIN
      type: File
  - name: numactl-lib
    hostPath:
      path: $NUMACTL_LIB
      type: File
EOF
}

# ============================================================
# RUN SCENARIO
# ============================================================
run_scenario() {
    local scenario=$1 pod="redis-$scenario" prefix="$RESULTS_DIR/$scenario"
    local start=$(date +%s) end duration

    echo ""; echo "=========================================="
    echo -e "  SCENARIO: ${YELLOW}$scenario${NC}"
    echo "=========================================="

    log_info "[1/11] Deploying pod $pod..."
    build_manifest "$scenario" | kubectl apply -f -
    log_ok "Pod $pod created"

    log_info "[2/11] Waiting for Redis to start..."
    if ! wait_for_redis "$pod"; then
        kubectl delete pod "$pod" --grace-period=0 --force 2>/dev/null || true
        return 1
    fi

    log_info "[3/11] Verifying NUMA pinning..."
    kubectl exec "$pod" -- sh -c "numactl --show 2>/dev/null || echo 'numactl not available'"

    log_info "[4/11] Retrieving pod IP..."
    local ip=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.podIP}')
    [[ -z "$ip" ]] && { log_err "No pod IP"; return 1; }
    log_ok "Pod IP: $ip"

    log_info "[5/11] Starting perf on $WORKER_NODE..."
    local pid=$(kubectl exec "$pod" -- pgrep redis-server | head -1)
    log_info "redis-server PID: $pid"
    ssh "$WORKER_NODE" "sudo perf stat -e instructions,cycles,cache-misses,LLC-load-misses,cpu-clock -p $pid -o /tmp/perf_${scenario}.csv sleep $BENCHMARK_DURATION_SEC" &
    local perf_pid=$!
    log_ok "perf started (PID: $perf_pid, duration: ${BENCHMARK_DURATION_SEC}s)"

    log_info "[6/11] RAPL measurement (BEFORE)..."
    sleep 2; measure_rapl "${prefix}_rapl_before.csv" "BEFORE"

    log_info "[7/11] Running redis-benchmark..."
    log_info "    - 100,000 GET/SET requests, 50 clients, 1024B values"
    if kubectl run redis-bench --rm -i --restart=Never --image="$REDIS_IMAGE" --imagePullPolicy=IfNotPresent \
         -- redis-benchmark -h "$ip" -p 6379 -t get,set -n 100000 -c 50 -d 1024 \
         > "${prefix}_benchmark.txt" 2>&1; then
        log_ok "Benchmark completed"
    else
        log_warn "Benchmark error"
    fi

    log_info "[8/11] RAPL measurement (AFTER)..."
    measure_rapl "${prefix}_rapl_after.csv" "AFTER"

    log_info "[9/11] Waiting for perf..."
    if wait $perf_pid; then log_ok "perf completed"; else log_warn "perf error"; fi

    log_info "[10/11] Retrieving perf file..."
    if scp "$WORKER_NODE:/tmp/perf_${scenario}.csv" "${prefix}_perf.csv" 2>/dev/null; then
        log_ok "perf file retrieved"
    else
        log_warn "perf file not found"; touch "${prefix}_perf.csv"
    fi

    log_info "[11/11] Deleting pod $pod..."
    kubectl delete pod "$pod" --grace-period=0 --force 2>/dev/null || true

    end=$(date +%s); duration=$((end-start))
    log_ok "Scenario $scenario completed in ${duration}s"
    log_info "Stabilization pause (5s)..."; sleep 5
    return 0
}

# ============================================================
# SUMMARY
# ============================================================
show_summary() {
    echo ""; echo "=========================================="
    echo -e "  ${GREEN}EXPERIMENT SUMMARY${NC}"
    echo "=========================================="
    for s in "${SCENARIOS[@]}"; do
        local p="$RESULTS_DIR/$s"
        echo -e "${YELLOW}--- $s ---${NC}"
        if [[ -f "${p}_rapl_before.csv" && -f "${p}_rapl_after.csv" ]]; then
            echo "  Total energy: $(calc_energy "${p}_rapl_before.csv" "${p}_rapl_after.csv") J"
        else echo "  RAPL files missing"; fi
        if [[ -f "${p}_benchmark.txt" ]]; then
            local tg=$(grep -oP 'GET\s*.*?\s*\K[\d.]+(?=\s*requests per second)' "${p}_benchmark.txt" 2>/dev/null | head -1 || echo "N/A")
            local ts=$(grep -oP 'SET\s*.*?\s*\K[\d.]+(?=\s*requests per second)' "${p}_benchmark.txt" 2>/dev/null | head -1 || echo "N/A")
            [[ "$tg" == "N/A" ]] && tg=$(grep -oP 'throughput summary:\s*\K[\d.]+' "${p}_benchmark.txt" 2>/dev/null | head -1 || echo "N/A") && ts="$tg"
            echo "  Throughput GET: ${tg} req/s"; echo "  Throughput SET: ${ts} req/s"
        else echo "  Benchmark file missing"; fi
        if [[ -f "${p}_perf.csv" && -s "${p}_perf.csv" ]]; then
            local inst=$(grep -oP '[\d,]+(?=\s+instructions)' "${p}_perf.csv" 2>/dev/null | tr -d ',' | head -1)
            local cycles=$(grep -oP '[\d,]+(?=\s+cycles)' "${p}_perf.csv" 2>/dev/null | tr -d ',' | head -1)
            [[ -n "$inst" && -n "$cycles" && "$cycles" -gt 0 ]] && echo "  IPC: $(echo "scale=3; $inst/$cycles" | bc)"
        fi; echo ""
    done
    echo -e "${GREEN}Next step:${NC} python3 ~/k8s-numa-benchmark/scripts/redis/calculate_redis_metrics.py"; echo ""
}

# ============================================================
# MAIN
# ============================================================
main() {
    echo "=========================================="
    echo "  REDIS NUMA BENCHMARK SUITE"
    echo "  Worker: $WORKER_NODE"
    echo "  Image: $REDIS_IMAGE (with hostPath numactl)"
    echo "  Results: $RESULTS_DIR"
    echo "=========================================="
    check_prerequisites
    local start=$(date +%s)
    for s in "${SCENARIOS[@]}"; do
        if ! run_scenario "$s"; then log_err "Scenario $s failed. Moving on..."; fi
    done
    local end=$(date +%s)
    log_ok "All scenarios completed in $((end-start))s"
    show_summary
}

main "$@"