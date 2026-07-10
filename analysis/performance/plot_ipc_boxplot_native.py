#!/usr/bin/env python3
"""
plot_ipc_boxplot_native.py

Per-pod IPC boxplots: Native N4 vs Native Overload N16.
IPC = Σ(IPC × cycles) / Σ(cycles) per pod (weighted average by cycles).

Cleaned-up version with improved visual quality only.
No quality filters, no Mann-Whitney.
"""

import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

PERF_DIR = os.path.expanduser("~/sdn2_remote_data/diagnostics")

SCENARIO_MAP = [
    ("native-n4-seq",   "Sequential", "Native N4\n(reference)"),
    ("native-n16-seq",  "Sequential", "Native Overload N16"),
    ("native-n4-rand",  "Random",     "Native N4\n(reference)"),
    ("native-n16-rand", "Random",     "Native Overload N16"),
]

COLOR = {
    "Native N4\n(reference)": "#2471a3",
    "Native Overload N16":    "#e74c3c",
}


def load_data(perf_dir):
    records = []
    if not os.path.exists(perf_dir):
        print(f"[ERROR] Directory not found: {perf_dir}")
        return pd.DataFrame()

    for prefix, pattern, label in SCENARIO_MAP:
        for folder in sorted(os.listdir(perf_dir)):
            if folder.lower() != prefix:
                continue

            folder_path = os.path.join(perf_dir, folder)
            if not os.path.isdir(folder_path):
                continue

            csv_name = (
                "memory_benchmark_seq_work.csv"
                if pattern == "Sequential"
                else "memory_benchmark_rand_work.csv"
            )

            pod_dirs = sorted([
                d for d in os.listdir(folder_path)
                if os.path.isdir(os.path.join(folder_path, d))
            ], key=lambda d: os.path.getmtime(os.path.join(folder_path, d)))

            # For Native N4 seq, keep only the most recent 4 pods (single run)
            if label.startswith("Native N4") and pattern == "Sequential":
                pod_dirs = pod_dirs[-4:]

            if not pod_dirs:
                print(f"  [WARN] No pod sub-directories in {folder_path}")
                continue

            for pod_dir in pod_dirs:
                csv_path = os.path.join(folder_path, pod_dir, csv_name)
                if not os.path.exists(csv_path):
                    continue

                try:
                    df = pd.read_csv(csv_path)
                    if 'IPC' not in df.columns or 'cycles' not in df.columns:
                        continue

                    df = df[df['cycles'] > 0]
                    if df.empty:
                        continue

                    ipc = (df['IPC'] * df['cycles']).sum() / df['cycles'].sum()
                    records.append({
                        'Pattern':  pattern,
                        'Scenario': label,
                        'IPC':      ipc,
                    })
                except Exception as e:
                    print(f"  [WARN] {csv_path}: {e}")

    return pd.DataFrame(records)


def compute_cv(values):
    m = np.mean(values)
    return np.std(values) / m * 100 if m > 0 else 0


def plot_boxplots(df):
    os.makedirs("analysis", exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5))
    fig.suptitle(
        "Per-Pod IPC — Native N4 vs Native Overload N16\n"
        "IPC = Σ(IPC×cycles) / Σcycles per pod  ·  "
        "box = quartiles, line = median, whiskers = 1.5×IQR",
        fontsize=12.5, fontweight='bold'
    )

    scenario_order = ["Native N4\n(reference)", "Native Overload N16"]

    for ax, pattern in zip(axes, ["Sequential", "Random"]):
        sub = df[df['Pattern'] == pattern]
        if sub.empty:
            ax.set_title(f"{pattern} — no data")
            continue

        groups = [
            sub[sub['Scenario'] == s]['IPC'].values
            for s in scenario_order
        ]

        positions = [1, 2]

        bp = ax.boxplot(
            groups,
            positions=positions,
            widths=0.45,
            patch_artist=True,
            showfliers=False,
            medianprops=dict(color='black', linewidth=2.5),
            whiskerprops=dict(linewidth=1.5),
            capprops=dict(linewidth=1.5),
            boxprops=dict(linewidth=1.5),
        )

        for patch, scen in zip(bp['boxes'], scenario_order):
            patch.set_facecolor(COLOR[scen])
            patch.set_alpha(0.55)

        # Annotations : n, mean, CV
        for pos, vals, scen in zip(positions, groups, scenario_order):
            if len(vals) == 0:
                continue
            n = len(vals)
            cv = compute_cv(vals)
            mn = np.mean(vals)
            col = '#c0392b' if scen == "Native Overload N16" else '#1a5276'

            y_top = max(vals) * 1.03 if max(vals) > 0 else 1
            ax.text(
                pos, y_top,
                f"n={n}  mean={mn:.3f}  CV={cv:.0f}%",
                ha='center', va='bottom',
                fontsize=10.5, fontweight='bold', color=col,
                bbox=dict(boxstyle='round,pad=0.4',
                          facecolor='white', edgecolor=col, alpha=0.95)
            )

        # Delta IPC and CV ratio in subplot title
        if len(groups[0]) > 0 and len(groups[1]) > 0:
            mean_n4 = np.mean(groups[0])
            mean_n16 = np.mean(groups[1])
            drop_pct = (mean_n16 - mean_n4) / mean_n4 * 100
            cv_n4 = compute_cv(groups[0])
            cv_n16 = compute_cv(groups[1])
            cv_ratio = cv_n16 / cv_n4 if cv_n4 > 0 else float('inf')

            ax.set_title(
                f"{pattern} access pattern\n"
                f"ΔIPC mean = {drop_pct:+.1f}%   ·   "
                f"CV ratio (N16/N4) = ×{cv_ratio:.1f}",
                fontsize=11, fontweight='bold'
            )
        else:
            ax.set_title(f"{pattern} access pattern",
                         fontsize=11, fontweight='bold')

        ax.set_xticks(positions)
        ax.set_xticklabels(scenario_order, fontsize=10.5)
        ax.set_ylabel("Per-pod IPC  [Σ(IPC×cycles) / Σcycles]", fontsize=10.5)
        ax.set_xlim(0.4, 2.6)

        all_vals = np.concatenate([g for g in groups if len(g) > 0])
        if len(all_vals) > 0:
            ax.set_ylim(bottom=0, top=all_vals.max() * 1.20)
        ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    out = "analysis/ipc_boxplot_fairness.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    print(f"\n[OK] Plot saved: {out}")
    plt.close()


if __name__ == "__main__":
    print("=== Per-Pod IPC Boxplot ===\n")
    df = load_data(PERF_DIR)

    if df.empty:
        print("[ERROR] No data loaded. Check PERF_DIR.")
    else:
        print(f"\nRecords loaded: {len(df)}")
        print(df.groupby(['Pattern', 'Scenario'])['IPC'].describe().round(4))
        plot_boxplots(df)