#!/usr/bin/env python3
"""
plot_numa_distribution.py

Parses raw numastat text files and produces horizontal stacked barplots
showing per-pod NUMA memory distribution.

Shows that the k3s scheduler produces heterogeneous NUMA placements
spontaneously — some pods are well-localized, others are fragmented.
"""

import re
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── CONFIGURATION — adjust paths ──
SEQ_FILE  = "results/numastat/numastat_seq_N16.txt"
RAND_FILE = "results/numastat/numastat_rand_N16_3.txt"


def parse_numastat_txt(path):
    """
    Parses the raw numastat text file format:
      PID (python3)    Node0_MB    Node1_MB    Total_MB
    Returns list of dicts sorted by minority_ratio.
    """
    if not os.path.exists(path):
        print(f"  [ERROR] File not found: {path}")
        return []

    pods = []
    with open(path) as f:
        for line in f:
            # Match lines like: 34748 (python3)    12.64    85.45    98.09
            m = re.match(
                r'\s*(\d+)\s+\(\w+\)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',
                line
            )
            if m:
                pid   = int(m.group(1))
                node0 = float(m.group(2))
                node1 = float(m.group(3))
                total = float(m.group(4))
                if total <= 0:
                    continue

                minority = min(node0, node1) / total * 100
                dominant = 0 if node0 >= node1 else 1

                pods.append({
                    'pid':            pid,
                    'node0_mb':       node0,
                    'node1_mb':       node1,
                    'total_mb':       total,
                    'minority_pct':   minority,
                    'dominant_node':  dominant,
                    'node0_pct':      node0 / total * 100,
                    'node1_pct':      node1 / total * 100,
                })

    # Sort by minority ratio (most localized first)
    pods.sort(key=lambda p: p['minority_pct'])
    print(f"  [OK] {os.path.basename(path)}: {len(pods)} pods parsed")
    return pods


def plot_distribution(seq_pods, rand_pods):
    os.makedirs("analysis", exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    fig.suptitle(
        "NUMA Memory Distribution Per Pod — Native Overload N=16\n"
        "k3s scheduler without NUMA constraints  |  "
        "Sorted by memory fragmentation (minority ratio)",
        fontsize=12, fontweight='bold'
    )

    datasets = [
        (axes[0], seq_pods,  "Sequential N16", "#2471a3", "#5dade2"),
        (axes[1], rand_pods, "Random N16",     "#c0392b", "#e74c3c"),
    ]

    for ax, pods, title, color0, color1 in datasets:
        if not pods:
            ax.set_title(f"{title} — no data")
            continue

        n = len(pods)
        y_pos = np.arange(n)

        # Stacked horizontal bars: Node0 (left) + Node1 (right)
        node0_pcts = [p['node0_pct'] for p in pods]
        node1_pcts = [p['node1_pct'] for p in pods]
        labels     = [f"PID {p['pid']}" for p in pods]

        bars0 = ax.barh(y_pos, node0_pcts, height=0.7,
                        color=color0, alpha=0.8,
                        edgecolor='white', linewidth=0.5,
                        label='NUMA Node 0')
        bars1 = ax.barh(y_pos, node1_pcts, height=0.7,
                        left=node0_pcts,
                        color=color1, alpha=0.8,
                        edgecolor='white', linewidth=0.5,
                        label='NUMA Node 1')

        # Annotate minority ratio on each bar
        for i, pod in enumerate(pods):
            minority = pod['minority_pct']
            # Place text at the end of the bar
            ax.text(102, i,
                    f"  {minority:.1f}%",
                    va='center', ha='left', fontsize=8,
                    color='darkred' if minority > 30 else 'black',
                    fontweight='bold' if minority > 30 else 'normal')

            # Show MB values inside the bars
            if pod['node0_pct'] > 15:
                ax.text(pod['node0_pct'] / 2, i,
                        f"{pod['node0_mb']:.0f}",
                        va='center', ha='center', fontsize=7,
                        color='white', fontweight='bold')
            if pod['node1_pct'] > 15:
                ax.text(pod['node0_pct'] + pod['node1_pct'] / 2, i,
                        f"{pod['node1_mb']:.0f}",
                        va='center', ha='center', fontsize=7,
                        color='white', fontweight='bold')

        # 50/50 reference line
        ax.axvline(x=50, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.text(50, n + 0.3, '50/50', ha='center', fontsize=8, color='gray')

        # Stats
        minorities = [p['minority_pct'] for p in pods]
        n_fragmented = sum(1 for m in minorities if m > 30)
        ax.text(0.98, 0.02,
                f"Pods with minority > 30%: {n_fragmented}/{n}\n"
                f"Min: {min(minorities):.1f}%  Max: {max(minorities):.1f}%\n"
                f"Mean: {np.mean(minorities):.1f}%",
                transform=ax.transAxes,
                ha='right', va='bottom', fontsize=9,
                bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))

        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("Memory distribution (%)", fontsize=10)
        ax.set_xlim(0, 118)  # extra space for annotations
        ax.set_title(f"{title}", fontsize=11, fontweight='bold')
        ax.legend(fontsize=9, loc='upper left')
        ax.invert_yaxis()  # most localized on top
        ax.grid(axis='x', alpha=0.25)

        # Column header for minority ratio
        ax.text(110, -0.8, 'minority\nratio',
                ha='center', va='bottom', fontsize=8,
                fontweight='bold', color='gray')

    plt.tight_layout()
    out = "analysis/numa_distribution_per_pod.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    print(f"\n[OK] Plot saved: {out}")
    plt.close()

    # ── Print summary table ──
    print(f"\n{'='*60}")
    print("  SUMMARY — NUMA Memory Distribution")
    print(f"{'='*60}")

    for label, pods in [("Sequential N16", seq_pods), ("Random N16", rand_pods)]:
        if not pods:
            continue
        minorities = [p['minority_pct'] for p in pods]
        n_frag = sum(1 for m in minorities if m > 30)
        print(f"\n  {label}:")
        print(f"    Pods: {len(pods)}")
        print(f"    Minority ratio: min={min(minorities):.1f}%  "
              f"max={max(minorities):.1f}%  mean={np.mean(minorities):.1f}%")
        print(f"    Fragmented (>30%): {n_frag}/{len(pods)} pods")
        print(f"    Well-localized (<20%): "
              f"{sum(1 for m in minorities if m < 20)}/{len(pods)} pods")


if __name__ == "__main__":
    print("=== NUMA Memory Distribution Analysis ===\n")
    seq_pods  = parse_numastat_txt(SEQ_FILE)
    rand_pods = parse_numastat_txt(RAND_FILE)

    if seq_pods or rand_pods:
        plot_distribution(seq_pods, rand_pods)
    else:
        print("[ERROR] No data loaded. Check file paths.")
        print(f"  SEQ_FILE  = {SEQ_FILE}")
        print(f"  RAND_FILE = {RAND_FILE}")