"""
Generates a detailed table (mean, standard deviation, CV%) of total power,
components (PKG0/PKG1/DRAM0/DRAM1) and duration, from one or more matmul
RAPL campaign CSV files (format: pattern,cores,scenario,duration_s,total_uj,
pkg0_uj,pkg1_uj,dram0_uj,dram1_uj).

The workload type is automatically detected from the 'pattern' column of
each file (e.g. 'matmul' -> GEMM, 'matmul-gemv' -> GEMV): a separate table
is generated per detected workload, even if several files/workloads are
passed as input in the same run of the script.

Usage:
    python3 generate_matmul_power_tables.py
"""

import pandas as pd
import numpy as np
import os

# ============================================================
# CONFIGURATION - adapt to your real paths on sdn4
# ============================================================

INPUT_FILES = [
    "results/RAPL/matmul_energy_results.csv",       # GEMM
    "results/RAPL/matmul_gemv_energy_results.csv",  # GEMV
]

OUTPUT_DIR = "results/RAPL/tables"

# Preferred display order for scenarios (scenarios absent from the dataset
# are simply skipped, no error raised)
SCENARIO_ORDER = ['baseline', 'extreme', 'cross-numa', 'extreme-cross', 'native']


# ============================================================
# LOADING
# ============================================================

def load_file(path):
    if not os.path.exists(path):
        print(f"[WARN] File not found, skipped: {path}")
        return None
    df = pd.read_csv(path)
    required = {'pattern', 'cores', 'scenario', 'duration_s', 'pkg0_uj', 'pkg1_uj', 'dram0_uj', 'dram1_uj'}
    missing = required - set(df.columns)
    if missing:
        print(f"[WARN] Missing columns in {path}: {missing} -> file skipped")
        return None
    return df


# ============================================================
# PER-COMPONENT POWER COMPUTATION (never from the raw total_uj column)
# ============================================================

def compute_power_components(df):
    df = df.copy()
    df['power_total_w'] = (df['pkg0_uj'] + df['pkg1_uj'] + df['dram0_uj'] + df['dram1_uj']) / df['duration_s'] / 1e6
    df['pkg0_w'] = df['pkg0_uj'] / df['duration_s'] / 1e6
    df['pkg1_w'] = df['pkg1_uj'] / df['duration_s'] / 1e6
    df['dram0_w'] = df['dram0_uj'] / df['duration_s'] / 1e6
    df['dram1_w'] = df['dram1_uj'] / df['duration_s'] / 1e6
    return df


# ============================================================
# AGGREGATION: mean, std, CV% per scenario (no flag column)
# ============================================================

def stat(vals, n):
    m = np.mean(vals)
    s = np.std(vals, ddof=1) if n > 1 else np.nan
    cv = 100 * s / m if n > 1 else np.nan
    return round(m, 2), (round(s, 2) if n > 1 else None), (round(cv, 2) if n > 1 else None)


def aggregate(group):
    n = len(group)
    p_m, p_s, p_cv = stat(group['power_total_w'], n)
    pkg0_m, pkg0_s, pkg0_cv = stat(group['pkg0_w'], n)
    pkg1_m, pkg1_s, pkg1_cv = stat(group['pkg1_w'], n)
    dram0_m, dram0_s, dram0_cv = stat(group['dram0_w'], n)
    dram1_m, dram1_s, dram1_cv = stat(group['dram1_w'], n)
    d_m, d_s, d_cv = stat(group['duration_s'], n)

    return pd.Series({
        'n_runs': n,
        'power_mean_W': p_m, 'power_std_W': p_s, 'power_cv_%': p_cv,
        'pkg0_mean_W': pkg0_m, 'pkg0_std_W': pkg0_s, 'pkg0_cv_%': pkg0_cv,
        'pkg1_mean_W': pkg1_m, 'pkg1_std_W': pkg1_s, 'pkg1_cv_%': pkg1_cv,
        'dram0_mean_W': dram0_m, 'dram0_std_W': dram0_s, 'dram0_cv_%': dram0_cv,
        'dram1_mean_W': dram1_m, 'dram1_std_W': dram1_s, 'dram1_cv_%': dram1_cv,
        'duration_mean_s': d_m, 'duration_std_s': d_s, 'duration_cv_%': d_cv,
    })


def build_table(df):
    table = df.groupby(['scenario', 'pattern', 'cores']).apply(aggregate).reset_index()
    table['scenario'] = pd.Categorical(table['scenario'], categories=SCENARIO_ORDER, ordered=True)
    table = table.sort_values('scenario').reset_index(drop=True)
    return table


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_frames = []
    for path in INPUT_FILES:
        df = load_file(path)
        if df is not None:
            all_frames.append(df)

    if not all_frames:
        raise ValueError("No valid file found. Check INPUT_FILES at the top of the script.")

    full_df = pd.concat(all_frames, ignore_index=True)
    full_df = compute_power_components(full_df)

    # One table per distinct 'pattern' value (= one per detected workload)
    workloads = full_df['pattern'].unique()
    print(f"[INFO] Detected workloads: {list(workloads)}")

    for workload in workloads:
        subset = full_df[full_df['pattern'] == workload]
        table = build_table(subset)

        # Safe filename (replaces non-alphanumeric characters)
        safe_name = "".join(c if c.isalnum() else "_" for c in workload)
        out_csv = os.path.join(OUTPUT_DIR, f"table_power_{safe_name}.csv")
        out_md = os.path.join(OUTPUT_DIR, f"table_power_{safe_name}.md")

        table.to_csv(out_csv, index=False)
        with open(out_md, 'w') as f:
            f.write(f"# Detailed power/component table - workload: {workload}\n\n")
            f.write(table.to_markdown(index=False))

        print(f"\n[SUCCESS] Table '{workload}' -> {out_csv} / {out_md}")
        print(table.to_string(index=False))