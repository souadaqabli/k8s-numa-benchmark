#!/usr/bin/env python3
"""
plot_ipc_boxplot.py

Per-pod IPC boxplots: Native N4 vs Native Overload N16.
IPC = Σ(IPC × cycles) / Σ(cycles)  [weighted average by cycles]
"""

import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

PERF_DIR = os.path.expanduser("~/sdn2_remote_data/diagnostics")

# Only these exact prefixes are loaded — N6, N8, N10, N12, N20 are excluded
SCENARIO_MAP = [
    ("native-n4-seq",   "Sequential", "Native N4\n(reference)"),
    ("native-n16-seq",  "Sequential", "Native Overload N16"),
    ("native-n4-rand",  "Random",     "Native N4\n(reference)"),
    ("native-n16-rand", "Random",     "Native Overload N16"),
]

# Colors
COLOR = {
    "Native N4\n(reference)": "#2471a3",
    "Native Overload N16":    "#e74c3c",
}


def load_data(perf_dir):
    records = []
    for prefix, pattern, label in SCENARIO_MAP:
        # Match folders that START with the prefix (handles -2, -3 variants)
        for folder in sorted(os.listdir(perf_dir)):
            if not folder.lower().startswith(prefix):
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
            ])

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

                    # Weighted-average IPC
                    ipc = (df['IPC'] * df['cycles']).sum() / df['cycles'].sum()
                    records.append({
                        'Pattern': pattern,
                        'Scenario': label,
                        'IPC': ipc,
                    })
                except Exception as e:
                    print(f"  [WARN] {csv_path}: {e}")

    return pd.DataFrame(records)


def compute_cv(values):
    m = np.mean(values)
    return np.std(values) / m * 100 if m > 0 else 0


def plot_boxplots(df):
    os.makedirs("analysis", exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    fig.suptitle(
        "Per-Pod IPC — Native N4 vs Native Overload N16\n"
        "IPC = Σ(IPC×cycles) / Σcycles  |  Each point = one pod",
        fontsize=13, fontweight='bold'
    )

    scenario_order = ["Native N4\n(reference)", "Native Overload N16"]

    for ax, pattern in zip(axes, ["Sequential", "Random"]):
        sub = df[df['Pattern'] == pattern]
        if sub.empty:
            ax.set_title(f"{pattern} — no data")
            continue

        # Collect data in fixed order
        groups = [
            sub[sub['Scenario'] == s]['IPC'].values
            for s in scenario_order
        ]

        positions = [1, 2]

        # ── Boxplot ──
        bp = ax.boxplot(
            groups,
            positions=positions,
            widths=0.45,
            patch_artist=True,
            showfliers=False,          # outliers shown as individual points below
            medianprops=dict(color='black', linewidth=2.5),
            whiskerprops=dict(linewidth=1.5),
            capprops=dict(linewidth=1.5),
            boxprops=dict(linewidth=1.5),
        )

        # Color each box
        for patch, scen in zip(bp['boxes'], scenario_order):
            patch.set_facecolor(COLOR[scen])
            patch.set_alpha(0.45)

        # ── Individual points (strip plot with fixed jitter) ──
        np.random.seed(42)   # reproducible jitter
        for pos, vals, scen in zip(positions, groups, scenario_order):
            jitter = np.random.uniform(-0.14, 0.14, size=len(vals))
            ax.scatter(
                pos + jitter, vals,
                color=COLOR[scen],
                s=55, alpha=0.85, zorder=5,
                edgecolors='black', linewidths=0.6
            )

        # ── Annotations : n, mean, CV ──
        y_max = max(g.max() for g in groups if len(g) > 0)
        y_ann = y_max * 1.06

        for pos, vals, scen in zip(positions, groups, scenario_order):
            n   = len(vals)
            cv  = compute_cv(vals)
            mn  = np.mean(vals)
            med = np.median(vals)
            col = 'darkred' if (scen == "Native Overload N16" and cv > 5) else '#1a5276'
            ax.text(
                pos, y_ann,
                f"n={n}\nmean={mn:.3f}\nCV={cv:.1f}%",
                ha='center', va='bottom',
                fontsize=9, fontweight='bold', color=col,
                bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.6)
            )

        # ── CV ratio ──
        cv_n4  = compute_cv(groups[0])
        cv_n16 = compute_cv(groups[1])
        ratio  = cv_n16 / cv_n4 if cv_n4 > 0 else 0
        ratio_col = 'darkred' if ratio > 1.5 else 'darkorange'
        ax.text(
            0.98, 0.03,
            f"CV ratio N16/N4 = ×{ratio:.1f}",
            transform=ax.transAxes,
            ha='right', va='bottom', fontsize=9,
            color=ratio_col, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.7)
        )

        # ── Mann-Whitney test ──
        if len(groups[0]) >= 2 and len(groups[1]) >= 2:
            u, p = stats.mannwhitneyu(
                groups[0], groups[1], alternative='two-sided')
            sig = "p < 0.05 ✓" if p < 0.05 else f"p={p:.3f} (n.s.)"
            ax.text(
                0.02, 0.97,
                f"Mann-Whitney: {sig}",
                transform=ax.transAxes,
                ha='left', va='top', fontsize=8.5,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.7)
            )

        # ── IPC drop annotation (arrow) ──
        mean_n4  = np.mean(groups[0])
        mean_n16 = np.mean(groups[1])
        drop_pct = (mean_n16 - mean_n4) / mean_n4 * 100
        ax.annotate(
            f"IPC drop\n{drop_pct:+.1f}%",
            xy=(2, mean_n16), xytext=(1.5, (mean_n4 + mean_n16) / 2),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.5),
            fontsize=9, ha='center', color='black',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.7)
        )

        ax.set_xticks(positions)
        ax.set_xticklabels(scenario_order, fontsize=10)
        ax.set_ylabel("Per-pod IPC  [Σ(IPC×cycles) / Σcycles]", fontsize=10)
        ax.set_title(f"{pattern} access pattern", fontsize=11, fontweight='bold')
        ax.set_xlim(0.4, 2.6)
        ax.set_ylim(bottom=0, top=y_ann * 1.35)
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
        print("[ERROR] No data loaded.")
    else:
        print(f"Records loaded: {len(df)}\n")
        print(df.groupby(['Pattern', 'Scenario'])['IPC'].describe().round(4))
        plot_boxplots(df)