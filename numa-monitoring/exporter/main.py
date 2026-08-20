import time
from prometheus_client import start_http_server
# Import the metrics registry
import metrics
# Import all custom collectors
from collectors.container_discovery import get_active_pods
from collectors.numa_collector import collect_numa
from collectors.perf_collector import collect_perf_for_finished_pods
from collectors.rapl_collector import collect_rapl
from garbage_collector import clean_dead_pods


def main():
    print("Starting NUMA-Aware Benchmark Exporter on port 9200...")
    start_http_server(9200)

    # Memory dict to store the previous state (pod scanning)
    previous_pods = {}

    # --- Current "run" state (energy + instructions accumulation) ---
    # A run = the window between the first pod of a Job appearing and the
    # last pod of the same Job disappearing. We accumulate RAPL energy and
    # instructions over that entire window, exactly like the manual method
    # already validated (generate_matmul_energy_efficiency_tables.py):
    # nJ/inst = total_run_energy / total_run_instructions
    job_active = False
    job_energy_uj = 0.0
    job_instructions = 0.0
    job_scenario = "unknown"
    # Tracks POD NAMES already processed for the current run, so a pod can
    # never be counted twice. Filtering by pod_name rather than PID because
    # the same pod can be reported under a different PID across consecutive
    # scans (container_discovery.py sometimes resolves the parent PID and
    # sometimes the true worker child PID for the same pod, depending on
    # exact timing) -> filtering by PID alone fails to catch that case.
    job_processed_pod_names = set()

    while True:
        # 1. Check which pods are running NOW
        current_pods = get_active_pods()
        metrics.ACTIVE_PODS.set(len(current_pods))

        # 2. Detect the START of a run: the cluster was empty, pods just
        # appeared -> reset the run counters
        if current_pods and not job_active:
            job_active = True
            job_energy_uj = 0.0
            job_instructions = 0.0
            job_scenario = list(current_pods.values())[0]
            job_processed_pod_names = set()
            print(f"[Job] New run detected: {job_scenario}")

        # 3. Detect which pods have just disappeared
        finished_pods = {pid: name for pid, name in previous_pods.items() if pid not in current_pods}

        # 3bis. Filter out pod NAMES already processed for this run, to
        # avoid double-counting a pod's instructions if it gets reported
        # under a different PID across scans.
        finished_pods = {pid: name for pid, name in finished_pods.items() if name not in job_processed_pod_names}

        # 4. If a pod has just finished, its CSV is ready. Read it and
        # accumulate its instructions into the current run's total.
        if finished_pods:
            job_instructions += collect_perf_for_finished_pods(finished_pods)
            job_processed_pod_names.update(finished_pods.values())

        # 5. Collect real-time metrics for the pods that are still running
        collect_numa(current_pods)

        # 6. Collect global RAPL metrics (returns the energy delta since the
        # last tick, in uJ) and accumulate it into the current run's total
        energy_delta_uj = collect_rapl()
        if job_active:
            job_energy_uj += energy_delta_uj

        # 7. Detect the END of a run: there were pods before, none now ->
        # compute and publish the final nJ/instruction value
        if job_active and not current_pods:
            job_active = False
            if job_instructions > 0:
                energy_j = job_energy_uj / 1_000_000.0
                nj_per_instruction = (energy_j * 1_000_000_000.0) / job_instructions
                metrics.JOB_ENERGY_NJ_PER_INSTRUCTION.labels(scenario=job_scenario).set(nj_per_instruction)
                print(f"[Job] Run finished ({job_scenario}): "
                      f"{energy_j:.1f} J / {job_instructions:.3e} instructions "
                      f"= {nj_per_instruction:.2f} nJ/inst")
            else:
                print(f"[Job] Run finished ({job_scenario}) but no instructions "
                      f"were recorded -> nJ/inst not computed")

        # 8. Clean up dead pods from Prometheus registry
        clean_dead_pods(previous_pods, current_pods)

        # 9. Update the memory for the next loop iteration
        previous_pods = current_pods

        time.sleep(5)


if __name__ == '__main__':
    main()
