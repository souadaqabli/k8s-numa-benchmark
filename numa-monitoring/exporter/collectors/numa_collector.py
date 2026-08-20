import os
import glob
import metrics

def get_cpu_numa_node(cpu_core):
    """Finds the physical NUMA node (0 or 1) for a specific CPU core."""
    try:
        node_paths = glob.glob(f"/sys/devices/system/cpu/cpu{cpu_core}/node*")
        if node_paths:
            node_dir = os.path.basename(node_paths[0])
            return int(node_dir.replace('node', ''))
    except:
        pass
    return 0

def collect_numa(current_pods):
    for pid, pod_name in current_pods.items():
        pid_str = str(pid)
        try:
            # 1. CPU Core Placement
            stat_file = f"/proc/{pid}/stat"
            if os.path.exists(stat_file):
                with open(stat_file, 'r') as f:
                    stat_data = f.read().split()
                    if len(stat_data) > 38:
                        cpu_core = int(stat_data[38])
                        numa_node = get_cpu_numa_node(cpu_core)

                        metrics.POD_CPU_CORE.labels(pod_name=pod_name, pid=pid_str).set(cpu_core)
                        metrics.POD_CPU_NUMA_NODE.labels(pod_name=pod_name, pid=pid_str).set(numa_node)

            # 2. NUMA Memory Distribution
            numa_maps_file = f"/proc/{pid}/numa_maps"
            node0_pages = 0
            node1_pages = 0

            if os.path.exists(numa_maps_file):
                with open(numa_maps_file, 'r') as f:
                    for line in f:
                        if 'N0=' in line:
                            node0_pages += int(line.split('N0=')[1].split()[0])
                        if 'N1=' in line:
                            node1_pages += int(line.split('N1=')[1].split()[0])

            node0_mb = (node0_pages * 4) / 1024.0
            node1_mb = (node1_pages * 4) / 1024.0

            metrics.POD_NUMA_NODE0.labels(pod_name=pod_name, pid=pid_str).set(node0_mb)
            metrics.POD_NUMA_NODE1.labels(pod_name=pod_name, pid=pid_str).set(node1_mb)

        except Exception as e:
            print(f"[NUMA Collector] Error for PID {pid}: {e}")
