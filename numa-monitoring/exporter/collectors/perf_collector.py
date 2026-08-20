import os
import glob
import csv
import time
import metrics

HOST_RESULTS_DIR = "/home/sdnuser/k8s-numa-benchmark/results"


def get_expected_csv_name(pod_name):
    """Infers the CSV file name based on the pod name."""
    if "matmul" in pod_name:
        if "gemv" in pod_name:
            return "matmul_benchmark_gemv_work.csv"
        return "matmul_benchmark_gemm_work.csv"
    elif "rand" in pod_name:
        return "memory_benchmark_rand_work.csv"
    elif "seq" in pod_name:
        return "memory_benchmark_seq_work.csv"
    return None


def collect_perf_for_finished_pods(finished_pods):
    """Reads the CSV only for pods that have just terminated.

    Returns the total number of instructions (IPC * cycles) accumulated
    across all pods processed in this call, so the caller (main.py) can
    add it to the current run's running total -> nJ/instruction is then
    computed as total_run_energy / total_run_instructions, the same
    method already validated manually in
    generate_matmul_energy_efficiency_tables.py.
    """
    total_instructions = 0.0

    # 1. Give Kubernetes 2 seconds to flush the CSV to the disk
    time.sleep(2)

    for pid, pod_name in finished_pods.items():
        print(f"[Perf] Detected finished pod: {pod_name}. Searching for CSV...")
        csv_name = get_expected_csv_name(pod_name)
        if not csv_name:
            print(f"[Perf] Warning: Unrecognized pod type, skipping {pod_name}")
            continue

        pod_id = pod_name.split('-')[-1]
        search_pattern = os.path.join(HOST_RESULTS_DIR, f"**/*{pod_id}*", csv_name)
        matches = glob.glob(search_pattern, recursive=True)
        if not matches:
            print(f"[Perf] ERROR: NO MATCH FOUND for pattern: {search_pattern}")
            continue

        csv_path = matches[0]
        print(f"[Perf] Found CSV: {csv_path}")

        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if not rows:
                    print(f"[Perf] ERROR: CSV file is empty: {csv_path}")
                    continue
                last_row = rows[-1]

                # --- IPC / stalls (unchanged from the original version) ---
                ipc = 0.0
                if 'IPC' in last_row:
                    ipc = float(last_row['IPC'])
                    metrics.POD_IPC.labels(pod_name=pod_name).set(ipc)
                if 'stalled_backend' in last_row:
                    metrics.POD_STALLS_BACKEND.labels(pod_name=pod_name).set(float(last_row['stalled_backend']))
                if 'stalled_frontend' in last_row:
                    metrics.POD_STALLS_FRONTEND.labels(pod_name=pod_name).set(float(last_row['stalled_frontend']))

                # --- NEW: instructions = IPC * cycles, accumulated for the run ---
                if 'cycles' in last_row and ipc > 0:
                    cycles = float(last_row['cycles'])
                    total_instructions += ipc * cycles
                else:
                    print(f"[Perf] WARNING: missing 'cycles' column or IPC<=0 for "
                          f"{pod_name}, this pod's instructions are NOT counted "
                          f"in the run total (columns found: {list(last_row.keys())})")

            print(f"[Perf] SUCCESS: Metrics extracted to Prometheus for {pod_name}")
        except Exception as e:
            print(f"[Perf] CRITICAL ERROR: Cannot read CSV for {pod_name}: {e}")

    return total_instructions
