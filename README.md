# K8s NUMA Benchmark

Measuring the energy cost of NUMA placement decisions in Kubernetes.

This project quantifies how pod scheduling choices affect energy efficiency on a dual-socket machine, using RAPL energy counters and hardware performance counters (`perf stat`) to produce a single, interpretable metric: **nJ per instruction**.

## Research Question

Does NUMA-unaware scheduling in Kubernetes produce a measurable and reproducible degradation in energy efficiency?

## Hardware Setup

| Parameter | Value |
|-----------|-------|
| Node | sdn2 |
| Sockets | 2 × Intel (NUMA node 0 and NUMA node 1) |
| Physical cores | 6 per socket = 12 total |
| Logical cores (HT) | 24 |
| RAM | ~30 GB (~15 GB per NUMA node) |

## Measurement Methodology

Each experiment measures two quantities simultaneously:

- **RAPL** — node-level energy in µJ, read from `/sys/class/powercap/intel-rapl:*/energy_uj` across four channels: `PKG0`, `PKG1`, `DRAM0`, `DRAM1`
- **perf stat** — per-pod hardware counters: `instructions`, `cycles`, `LLC-load-misses`, `IPC`

The target metric is:

```
nJ/instruction = (E_total × 10⁹) / Σ instructions_across_pods
```

This normalises energy by useful work done, making scenarios with different pod counts directly comparable.

## Experiment Scenarios

### Controlled (numactl-pinned, 4 pods)

| Scenario | CPU binding | Memory binding | Description |
|----------|-------------|----------------|-------------|
| **Baseline** | NUMA 0 | NUMA 0 | Optimal local placement |
| **Extreme** | NUMA 0 (all 4 pods) | NUMA 0 | CPU contention, local memory |
| **Cross-NUMA** | NUMA 0 | NUMA 1 | Remote memory access forced |
| **Extreme-Cross** | NUMA 0 (all 4 pods) | NUMA 1 | CPU contention + remote memory |

Reference results (work-bound, 10 GB buffer):

| Scenario | Sequential nJ/inst | Random nJ/inst |
|----------|--------------------|----------------|
| Baseline | 8.89 | 30.97 |
| Extreme | 12.48 | 31.80 |
| Cross-NUMA | 13.91 | 46.46 |
| Extreme-Cross | 17.29 | 51.61 |

### Scalability (N4 to N20 pods, no numactl)

Same four scenarios run with increasing pod counts (N4, N6, N8, N10, N12) plus a `native` scenario where the k8s scheduler places pods freely. Used to study how energy efficiency degrades as the node is progressively overloaded.

### Overload (N16, N24)

16 or 24 pods on 12 physical cores — forces the scheduler to spill across sockets via Hyper-Threading. Used to isolate the energy cost of SMT contention.

## Memory Access Patterns

Every scenario is run in two modes:

- **Sequential** (`seq`) — large linear scan, bandwidth-bound
- **Random** (`rand`) — random pointer chasing, latency-bound

And two experiment modes:

- **Work-bound** — each pod processes a fixed total volume (e.g. 10 GB)
- **Time-bound** — each pod runs for a fixed duration

## Project Structure

```
k8s-numa-benchmark/
├── Dockerfile                  # Container image for benchmark pods
├── run_all.sh                  # Pod entrypoint (numactl + script_controlled.py)
│
├── scripts/
│   ├── script_controlled.py    # Main benchmark (NumPy sequential/random memory access)
│   ├── mem_stress_controlled.py
│   ├── generate_yaml.sh        # Generate scalability YAML manifests
│   ├── measure_tax.sh          # Measure scheduling overhead
│   ├── host/                   # Run on the measurement host (RAPL, campaign orchestration)
│   └── redis/                  # Redis NUMA benchmark
│
├── deployments/
│   ├── controlled/
│   │   ├── rand/               # 4-pod controlled scenarios — random pattern
│   │   └── seq/                # 4-pod controlled scenarios — sequential pattern
│   ├── scalability/
│   │   ├── rand/               # N4–N20 scalability — random
│   │   └── seq/                # N4–N20 scalability — sequential
│   ├── overload/               # N16 and N24 overload scenarios
│   ├── redis/                  # Redis benchmark manifests
│   └── legacy/                 # Older experimental manifests
│
├── analysis/
│   ├── energy/                 # RAPL energy plot scripts
│   ├── performance/            # perf stat plot scripts
│   ├── numa/                   # NUMA placement analysis (numastat, IPC correlation)
│   ├── tables/                 # Instruction extraction and summary CSV generation
│   └── correlation/
│       ├── v1/                 # First correlation approach (perf + RAPL)
│       └── v2/                 # Refined correlation approach
│
└── monitoring/                 # Scaphandre DaemonSet manifests (Prometheus energy scraping)
```

## Running an Experiment

### 1. Build the benchmark image

```bash
docker build -t memory-benchmark:v_numa4 .
```

### 2. Apply a scenario

```bash
# Controlled — 4-pod sequential baseline (work-bound)
kubectl apply -f deployments/controlled/seq/pods-optimal-4-seq-work.yaml

# Scalability — 10 pods, sequential, extreme contention
kubectl apply -f deployments/scalability/seq/N10/extreme.yaml
```

### 3. Collect results

Results are written to the host path `/home/sdnuser/k8s-numa-benchmark/results/` via a `hostPath` volume.

RAPL energy is measured from the host using the campaign scripts:

```bash
bash scripts/host/run_scalability_campaign.sh
bash scripts/host/run_overload_campaign.sh N16 seq 1
```

### 4. Run analysis

```bash
# Energy vs. pod count (scalability)
python3 analysis/energy/energy_vs_cores.py

# perf aggregated plots
python3 analysis/performance/generate_perf_plots.py

# NUMA placement correlation
python3 analysis/numa/analyze_correlation_overload.py
```

## Prerequisites

| Tool | Purpose |
|------|---------|
| Kubernetes / k3s | Pod scheduling |
| `numactl` | CPU and memory binding inside pods |
| `perf stat` | Per-pod hardware counters |
| Python 3.8+ | Benchmark scripts and analysis |
| NumPy | Memory workload generation |
| matplotlib, pandas, seaborn | Analysis plots |
| Docker | Building the benchmark image |

## Key Files

| File | Role |
|------|------|
| `scripts/script_controlled.py` | NumPy benchmark: sequential/random access, perf stat capture |
| `scripts/host/run_scalability_campaign.sh` | Orchestrates RAPL + kubectl for scalability experiments |
| `scripts/host/run_overload_campaign.sh` | Orchestrates overload experiments with numastat snapshots |
| `scripts/generate_yaml.sh` | Generates all scalability YAML manifests programmatically |
| `analysis/energy/generate_plots_rapl_instructions_scale.py` | nJ/instruction vs. pod count plots |
| `analysis/correlation/v2/correlation_perf_rapl_v2.py` | IPC / MPKI correlation with energy |
| `monitoring/` | Scaphandre manifests for continuous energy monitoring |
