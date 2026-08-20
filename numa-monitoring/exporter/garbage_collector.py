import metrics

def clean_dead_pods(known_pods, current_pods):
    """
    Removes Prometheus metrics for pods that have been terminated.
    Prevents "ghost" flatlines in Grafana when a Kubernetes job finishes.
    
    Args:
        known_pods (dict): {pid: pod_name} from the previous cycle
        current_pods (dict): {pid: pod_name} from the current cycle
    Returns:
        dict: The updated state (copy of current_pods)
    """
    # Find PIDs that were in known_pods but are no longer in current_pods
    dead_pids = set(known_pods.keys()) - set(current_pods.keys())
    
    for pid in dead_pids:
        pod_name = known_pods[pid]
        try:
            # Remove the specific label combinations from Prometheus registry
            metrics.POD_NUMA_NODE0.remove(pod_name, pid)
            metrics.POD_NUMA_NODE1.remove(pod_name, pid)
            metrics.POD_CPU_CORE.remove(pod_name, pid)
            metrics.POD_CPU_NUMA_NODE.remove(pod_name, pid)
            
            print(f"[Garbage Collector] Cleared metrics for terminated pod: {pod_name} (PID: {pid})")
        except KeyError:
            # Metric might not exist if the pod died before its first full measurement cycle
            pass
            
    # Return a fresh copy of the current pods to serve as the new baseline
    return current_pods.copy()
