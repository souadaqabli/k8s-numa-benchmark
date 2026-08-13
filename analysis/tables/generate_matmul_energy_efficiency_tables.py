"""
Generates a detailed nJ/instruction table (mean, std, CV%) per scenario, for
each matmul workload (GEMM, GEMV, or any future variant), by combining:

  1. RAPL campaign energy CSVs (pattern,cores,scenario,duration_s,total_uj,
     pkg0_uj,pkg1_uj,dram0_uj,dram1_uj) -- already on sdn4.
  2. Per-pod perf CSVs (matmul_benchmark_{op}_work.csv, one row each with
     an IPC and cycles column) -- on sdn2, reachable from sdn4 through the
     sshfs mount at ~/sdn2_remote_data.

KEY METHODOLOGICAL POINT -- read before trusting the output:
The perf CSVs are written under a POD_ID-based folder name, so there is no
explicit "run1"/"run2" marker to pair a given pod with a given RAPL energy
row. This script pairs them by CHRONOLOGICAL ORDER: within a scenario's
perf directory, pod CSV files are sorted by modification time and grouped
into chunks of PODS_PER_RUN (4 here); group 1 is assumed to correspond to
the 1st row of the matching RAPL CSV, group 2 to the 2nd row, etc. This
assumes:
  - Results are never deleted between campaign runs (only the Kubernetes
    Jobs/pods are deleted, not the hostPath results directory).
  - The RAPL CSV rows for a given scenario are in chronological run order
    (true here, since the campaign script appends with `>>`).
If the pod count doesn't divide evenly by PODS_PER_RUN, or doesn't match
the number of RAPL rows, a warning is printed and that scenario is skipped
rather than silently producing a wrong pairing.

Usage:
    python3 generate_matmul_energy_efficiency_tables.py
"""

import pandas as pd
import numpy as np
import os
import glob

# ============================================================
# CONFIGURATION - adapt to your real paths
# ============================================================

# RAPL campaign energy CSVs, already transferred to sdn4
RAPL_FILES = {
    "gemm": "results/RAPL/matmul_energy_results.csv",
    "gemv": "results/RAPL/matmul_gemv_energy_results.csv",
}

# Base path to the sshfs-mounted sdn2 results directory, seen from sdn4
PERF_BASE_DIR = os.path.expanduser("~/sdn2_remote_data/matmul")

# How each workload's scenario directory is named (relative to PERF_BASE_DIR),
# and the perf CSV filename to look for inside each pod's subfolder.
# Matches the run_all_matmul.sh / script_controlled_matmul.py naming
# convention: OUTPUT_DIR=/app/results/matmul/{scenario}[-gemv]/<pod folder>/
#             matmul_benchmark_{gemm|gemv}_work.csv
WORKLOAD_DIR_SUFFIX = {
    "gemm": "",       # e.g. results/matmul/baseline/
    "gemv": "-gemv",  # e.g. results/matmul/baseline-gemv/
}
WORKLOAD_CSV_NAME = {
    # GEMM jobs were launched BEFORE script_controlled_matmul.py was updated
    # to include MATMUL_OP in the filename, so their CSVs use the old,
    # unprefixed name. GEMV jobs were launched after that update.
    "gemm": "matmul_benchmark_gemm_work.csv",
    "gemv": "matmul_benchmark_gemv_work.csv",
}

SCENARIO_ORDER = ['baseline', 'extreme', 'cross-numa', 'extreme-cross', 'native']
PODS_PER_RUN = 4  # all 4 scenarios use 4 pods total at N4 in this setup

OUTPUT_DIR = "results/RAPL/tables"


# ============================================================
# STEP 1 - Load RAPL energy data (in chronological/file order per scenario)
# ============================================================

def load_rapl_runs(path):
    """Returns {scenario: [ (duration_s, pkg0_uj, pkg1_uj, dram0_uj, dram1_uj), ... ]}
    preserving the original row order (= chronological run order)."""
    if not os.path.exists(path):
        print(f"[WARN] RAPL file not found, skipped: {path}")
        return {}
    df = pd.read_csv(path)
    runs = {}
    for scenario, group in df.groupby('scenario', sort=False):
        runs[scenario] = list(zip(
            group['duration_s'], group['pkg0_uj'], group['pkg1_uj'],
            group['dram0_uj'], group['dram1_uj']
        ))
    return runs


# ============================================================
# STEP 2 - Find and group per-pod perf CSVs chronologically
# ============================================================

def find_pod_csvs(scenario, workload):
    """Finds all perf CSVs for a given scenario/workload under PERF_BASE_DIR,
    returns a list of (path, mtime) sorted by modification time (ascending)."""
    dir_name = scenario + WORKLOAD_DIR_SUFFIX[workload]
    csv_name = WORKLOAD_CSV_NAME[workload]
    pattern = os.path.join(PERF_BASE_DIR, dir_name, "*", csv_name)
    paths = glob.glob(pattern)
    if not paths:
        print(f"[WARN] No perf CSV found for pattern: {pattern}")
        return []
    files_with_mtime = [(p, os.path.getmtime(p)) for p in paths]
    files_with_mtime.sort(key=lambda x: x[1])
    return files_with_mtime


def group_into_runs(files_with_mtime, pods_per_run, verbose=True):
    """Splits a chronologically sorted file list into consecutive groups of
    `pods_per_run` files. Returns a list of groups (list of paths).
    If verbose, prints each group with human-readable timestamps so you can
    visually confirm the run boundaries look right (e.g. a clear time gap
    between group 1 and group 2) before trusting the final numbers."""
    import datetime
    paths = [p for p, _ in files_with_mtime]
    groups = [paths[i:i + pods_per_run] for i in range(0, len(paths), pods_per_run)]

    if verbose and files_with_mtime:
        print(f"  [CHECK] {len(files_with_mtime)} pod CSV(s) found, grouped into {len(groups)} run(s):")
        for run_idx, group in enumerate(groups, 1):
            for path in group:
                mtime = next(t for p, t in files_with_mtime if p == path)
                ts = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                print(f"    run{run_idx}: {ts}  {os.path.basename(os.path.dirname(path))}")
        print()

    return groups


def read_instructions(csv_path):
    """Reads a single-row perf CSV, returns instructions = IPC * cycles."""
    df = pd.read_csv(csv_path)
    row = df.iloc[0]
    return row['IPC'] * row['cycles']


def total_instructions_for_group(group_paths):
    return sum(read_instructions(p) for p in group_paths)


# ============================================================
# STEP 3 - Pair RAPL runs with perf run-groups, compute nJ/instruction
# ============================================================

def compute_nj_per_instruction_table(rapl_runs, workload):
    rows = []
    for scenario in SCENARIO_ORDER:
        if scenario not in rapl_runs:
            continue

        energy_runs = rapl_runs[scenario]
        n_rapl_runs = len(energy_runs)

        pod_files = find_pod_csvs(scenario, workload)
        run_groups = group_into_runs(pod_files, PODS_PER_RUN)

        if len(run_groups) != n_rapl_runs:
            print(f"[WARN] {workload}/{scenario}: {n_rapl_runs} RAPL run(s) but "
                  f"{len(run_groups)} perf run-group(s) detected ({len(pod_files)} "
                  f"pod CSVs / {PODS_PER_RUN} pods-per-run) -> scenario skipped, "
                  f"check PERF_BASE_DIR / PODS_PER_RUN or missing perf files.")
            continue

        nj_per_inst_runs = []
        for (duration_s, pkg0_uj, pkg1_uj, dram0_uj, dram1_uj), group in zip(energy_runs, run_groups):
            energy_J = (pkg0_uj + pkg1_uj + dram0_uj + dram1_uj) / 1e6
            instructions = total_instructions_for_group(group)
            nj_per_inst = (energy_J * 1e9) / instructions
            nj_per_inst_runs.append(nj_per_inst)

        n = len(nj_per_inst_runs)
        m = np.mean(nj_per_inst_runs)
        s = np.std(nj_per_inst_runs, ddof=1) if n > 1 else np.nan
        cv = 100 * s / m if n > 1 else np.nan

        rows.append({
            'workload': workload,
            'scenario': scenario,
            'n_runs': n,
            'nj_per_inst_mean': round(m, 2),
            'nj_per_inst_std': round(s, 2) if n > 1 else None,
            'nj_per_inst_cv_%': round(cv, 2) if n > 1 else None,
        })

    table = pd.DataFrame(rows)
    if len(table):
        table['scenario'] = pd.Categorical(table['scenario'], categories=SCENARIO_ORDER, ordered=True)
        table = table.sort_values('scenario').reset_index(drop=True)
    return table


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for workload, rapl_path in RAPL_FILES.items():
        print(f"\n{'=' * 60}\nWorkload: {workload}\n{'=' * 60}")

        rapl_runs = load_rapl_runs(rapl_path)
        if not rapl_runs:
            continue

        table = compute_nj_per_instruction_table(rapl_runs, workload)
        if table.empty:
            print(f"[WARN] No table could be built for workload '{workload}'.")
            continue

        out_csv = os.path.join(OUTPUT_DIR, f"table_nj_per_inst_{workload}.csv")
        out_md = os.path.join(OUTPUT_DIR, f"table_nj_per_inst_{workload}.md")
        table.to_csv(out_csv, index=False)
        with open(out_md, 'w') as f:
            f.write(f"# nJ/instruction table - workload: {workload}\n\n")
            f.write(table.to_markdown(index=False))

        print(f"[SUCCESS] -> {out_csv} / {out_md}")
        print(table.to_string(index=False))