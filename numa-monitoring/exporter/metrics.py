from prometheus_client import Gauge

# Hardware Global (RAPL)
RAPL_POWER = Gauge('rapl_power_watts', 'Current power consumption in Watts', ['domain'])
ACTIVE_PODS = Gauge('active_benchmark_pods', 'Number of running K3s benchmark pods')

# Pod Specific - RAM NUMA Allocation
POD_NUMA_NODE0 = Gauge('pod_numa_node0_mb', 'RAM allocated on NUMA Node 0 (MB)', ['pod_name', 'pid'])
POD_NUMA_NODE1 = Gauge('pod_numa_node1_mb', 'RAM allocated on NUMA Node 1 (MB)', ['pod_name', 'pid'])

# Pod Specific - CPU Pinning
POD_CPU_CORE = Gauge('pod_cpu_core', 'Current CPU core (PSR) executing the pod', ['pod_name', 'pid'])
POD_CPU_NUMA_NODE = Gauge('pod_cpu_numa_node', 'NUMA node executing the CPU process (0 or 1)', ['pod_name', 'pid'])

# Profilage Bas Niveau (Pour plus tard)
CPU_IPC = Gauge('cpu_ipc', 'Instructions Per Cycle')
CPU_STALL_RATE = Gauge('cpu_stall_rate_percent', 'Memory Stall Rate (%)')

POD_IPC = Gauge('pod_ipc', 'Instructions Per Cycle', ['pod_name'])
POD_STALLS_BACKEND = Gauge('pod_stalls_backend', 'Backend stall cycles', ['pod_name'])
POD_STALLS_FRONTEND = Gauge('pod_stalls_frontend', 'Frontend stall cycles', ['pod_name'])
JOB_ENERGY_NJ_PER_INSTRUCTION = Gauge(
    'job_energy_nj_per_instruction',
    'Energy per instruction for the last completed run (nJ)',
    ['scenario']
)
