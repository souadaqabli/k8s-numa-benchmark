# Exploring Memory Performance for Large Python Computations
## Project Overview
This research project characterizes the performance bottlenecks observed when running memory-intensive Python/NumPy workloads on Linux. The goal is to establish a deterministic link between high-level Python requests and low-level hardware performance counters to understand the "Memory Wall" effect.
## Key Features
Pathological Workload Generation: Benchmarks designed to stress the memory hierarchy through specific spatial/temporal locality patterns.

Metrological Refinements: Integration of Core Pinning, Subtractive Calibration, and deterministic memory reuse to isolate hardware signals from software noise.

Hardware Telemetry: Deep correlation with hardware counters via perf (LLC-load-misses, IPC, and Backend Stalls).
## Project Structure
- `scripts/`: Python benchmark scripts and analysis entrypoints.
- `run_all.sh`: Automation script to execute the full measurement suite.
- `deployments/`: Kubernetes and NUMA deployment manifests for cluster and container experiments.
- `results/`: Directory containing raw measurement data and performance profiles.
- `data/`: Source datasets, archives, and perf logs.
- `figures/`: Generated plots and visualization assets.
- `archive/`: Backup and legacy files moved out of the root workspace.
## Prerequisites & Installation
- OS: Linux (tested on Ubuntu 24.04 LTS).
- Dependencies: Python 3.12+, NumPy 1.26.4.
- Tools: linux-tools-common (for perf access).
