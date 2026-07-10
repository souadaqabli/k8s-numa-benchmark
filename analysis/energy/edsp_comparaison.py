#!/usr/bin/env python3
"""
plot_edp_v2.py

Computes EDP and ED²P at system level, then normalizes by total work volume.

EDP       = Total_Energy_J × Duration_s          (system level)
ED²P      = Total_Energy_J × Duration_s²         (system level)
EDP/Go    = EDP  / (N_pods × 120 Go)             (per unit of work)
ED²P/Go   = ED²P / (N_pods × 120 Go)             (per unit of work)

Volume per pod = 6 buffer sizes × 2 patterns (read+write) × 10 Go = 120 Go
"""

import os
import csv
import numpy as np
import matplotlib.pyplot as plt

RAPL_PATH = "results/RAPL/rapl_global_results_utiles.csv"

# Volume of work per pod in Go
# 6 buffer sizes × 2 access patterns (read + write) × 10 Go target per pass
GO_PER_POD = 6 * 2 * 10  # = 120 Go

# Number of pods per scenario
N_PODS = {
    'native-n4-seq':  4,
    'native-n4-rand': 4,
    'native-n16-seq': 16,
    'native-n16-rand': 16,
}


def load_rapl(csv_path):
    data = {}

    if not os.path.exists(csv_path):
        print(f"[ERROR] File not found: {csv_path}")
        return data

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].strip().lower() in ['scenario', 'pattern']:
                continue
            line = " ".join(row).lower()
            if 'native' not in line:
                continue
            if not any(x in line for x in ['n4', 'n16']):
                continue

            try:
                pattern   = row[0].strip().lower()
                cores_str = row[1].strip().lower()
                n_pods    = int(cores_str.replace('n', ''))
                duration  = float(row[3])

                # Total energy in Joules (columns 5-8 in µJ)
                total_J = sum(float(row[i]) for i in range(5, 9)) / 1_000_000

                # System-level metrics
                edp  = total_J * duration
                ed2p = total_J * duration ** 2

                # Total work volume for this run
                total_Go = n_pods * GO_PER_POD

                # Normalized metrics
                edp_per_Go  = edp  / total_Go
                ed2p_per_Go = ed2p / total_Go

                scenario = f"native-{cores_str}-{pattern}"
                if scenario not in data:
                    data[scenario] = []
                data[scenario].append({
                    'E_J':        total_J,
                    'T_s':        duration,
                    'EDP':        edp,
                    'ED2P':       ed2p,
                    'EDP_per_Go': edp_per_Go,
                    'ED2P_per_Go':ed2p_per_Go,
                    'n_pods':     n_pods,
                    'total_Go':   total_Go,
                })

            except (ValueError, IndexError):
                continue

    # Median over multiple runs
    result = {}
    for scen, runs in data.items():
        result[scen] = {k: np.median([r[k] for r in runs])
                        for k in runs[0].keys()}

    # Print summary
    print(f"\n{'Scenario':<22} {'E (J)':>10} {'T (s)':>7} "
          f"{'EDP':>12} {'EDP/Go':>12} {'ED²P':>14} {'ED²P/Go':>14}")
    print("-" * 95)
    for scen, v in sorted(result.items()):
        print(f"  {scen:<20} {v['E_J']:>10.1f} {v['T_s']:>7.0f} "
              f"{v['EDP']:>12.3e} {v['EDP_per_Go']:>12.3e} "
              f"{v['ED2P']:>14.3e} {v['ED2P_per_Go']:>14.3e}")

    return result


def plot(data):
    os.makedirs("analysis", exist_ok=True)

    labels   = ["Native (N4)", "Native Overload (N16)"]
    patterns = [
        ("Sequential", "native-n4-seq",  "native-n16-seq",
         "steelblue",  "cornflowerblue"),
        ("Random",     "native-n4-rand", "native-n16-rand",
         "tomato",     "salmon"),
    ]

    # ── Figure 1 : system-level EDP and ED²P ──
    fig1, axes1 = plt.subplots(2, 2, figsize=(13, 9))
    fig1.suptitle(
        "System-Level EDP & ED²P — Native N4 vs Native Overload N16\n"
        "(no normalization — raw system energy × time)",
        fontsize=13, fontweight='bold')

    # ── Figure 2 : normalized EDP and ED²P ──
    fig2, axes2 = plt.subplots(2, 2, figsize=(13, 9))
    fig2.suptitle(
        "Normalized EDP & ED²P per Go processed — Native N4 vs Native Overload N16\n"
        f"(volume per pod = {GO_PER_POD} Go  |  N4 total = {4*GO_PER_POD} Go"
        f"  |  N16 total = {16*GO_PER_POD} Go)",
        fontsize=13, fontweight='bold')

    for col, (pat_label, key_n4, key_n16, c_n4, c_n16) in enumerate(patterns):
        v_n4  = data.get(key_n4,  {})
        v_n16 = data.get(key_n16, {})

        for row, (metric_raw, metric_norm, unit_raw, unit_norm) in enumerate([
            ("EDP",  "EDP_per_Go",  "J·s",  "J·s / Go"),
            ("ED2P", "ED2P_per_Go", "J·s²", "J·s² / Go"),
        ]):
            label_raw  = "EDP"  if metric_raw == "EDP"  else "ED²P"
            label_norm = label_raw + " / Go"

            for fig, axes, metric, unit, label in [
                (fig1, axes1, metric_raw,  unit_raw,  label_raw),
                (fig2, axes2, metric_norm, unit_norm, label_norm),
            ]:
                ax = axes[row][col]
                vals   = [v_n4.get(metric, 0), v_n16.get(metric, 0)]
                colors = [c_n4, c_n16]

                bars = ax.bar(labels, vals, color=colors,
                              edgecolor='black', linewidth=0.8, width=0.5)

                for bar, v in zip(bars, vals):
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() * 1.02,
                            f'{v:.2e}',
                            ha='center', va='bottom',
                            fontsize=10, fontweight='bold')

                if vals[0] > 0:
                    ratio = vals[1] / vals[0]
                    color_ratio = 'darkred' if ratio > 1 else 'darkgreen'
                    ax.text(0.97, 0.95,
                            f'N16 / N4 = ×{ratio:.2f}',
                            transform=ax.transAxes,
                            ha='right', va='top', fontsize=9,
                            color=color_ratio,
                            bbox=dict(boxstyle='round',
                                      facecolor='lightyellow', alpha=0.7))

                ax.set_title(f"{pat_label} — {label} ({unit})",
                             fontsize=11, fontweight='bold')
                ax.set_ylabel(f"{label} ({unit})", fontsize=10)
                ax.yaxis.get_major_formatter().set_scientific(True)
                ax.yaxis.get_major_formatter().set_powerlimits((0, 0))
                ax.grid(axis='y', alpha=0.3)
                ax.set_ylim(0, max(vals) * 1.25 if max(vals) > 0 else 1)

    fig1.tight_layout()
    fig2.tight_layout()

    out1 = "analysis/edp_system_level.png"
    out2 = "analysis/edp_normalized_per_Go.png"
    fig1.savefig(out1, dpi=150, bbox_inches='tight')
    fig2.savefig(out2, dpi=150, bbox_inches='tight')
    print(f"\n[OK] System-level plot : {out1}")
    print(f"[OK] Normalized plot   : {out2}")
    plt.close('all')


if __name__ == "__main__":
    print("=== EDP / ED²P Analysis ===")
    data = load_rapl(RAPL_PATH)
    if data:
        plot(data)
    else:
        print("[ERROR] No data loaded.")