#!/usr/bin/env python3
"""
parse_and_plot_stalls.py

Parses perf stat -I output files and plots temporal evolution of:
  - IPC over time
  - Stall rate (stalls_mem_any / cycles) over time
  - CPI over time

Compares N4 vs N16 on the same axes for random and sequential patterns.
"""

import os
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

RESULTS_DIR = "./results/stalls"

# Files to load — adjust paths if needed
FILES = {
    'N4 Random':  'native_n4_rand_system.txt',
    'N16 Random': 'native_n16_rand_system.txt',
    'N4 Seq':     'native_n4_seq_system.txt',
    'N16 Seq':    'native_n16_seq_system.txt',
}

COLORS = {
    'N4 Random':  '#2471a3',
    'N16 Random': '#e74c3c',
    'N4 Seq':     '#1a8a2e',
    'N16 Seq':    '#f39c12',
}


def parse_perf_file(path):
    """
    Parses perf stat -I output.
    Returns DataFrame with columns:
        timestamp, cycles, instructions, ipc, cpi,
        stalls_mem_any, stalls_total, cycles_no_execute,
        stall_rate_mem, stall_rate_total
    """
    if not os.path.exists(path):
        print(f"  [MISS] {path}")
        return None

    records = {}  # timestamp -> {event: value}

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Format: timestamp   count   [unit]   event_name   [# comment]
            # count can be <not counted> or a number with commas
            m = re.match(
                r'(\d+\.\d+)\s+'           # timestamp
                r'([\d,]+|<not counted>)'  # count
                r'\s+(\S+)',               # event name (skip unit if present)
                line
            )
            if not m:
                continue

            ts    = float(m.group(1))
            count = m.group(2)
            # event name is after count — find it properly
            parts = line.split()
            # parts[0]=ts, parts[1]=count, then optional unit, then event
            # event is the first non-numeric, non-unit token after count
            event = None
            for i in range(2, len(parts)):
                p = parts[i]
                if p.startswith('cycle') or p in ('cycles', 'instructions'):
                    event = p
                    break
                if re.match(r'^[a-z_]', p) and p not in ('#', 'insn', 'per'):
                    event = p
                    break

            if event is None or count == '<not counted>':
                continue

            value = int(count.replace(',', ''))
            if ts not in records:
                records[ts] = {'timestamp': ts}
            records[ts][event] = value

    if not records:
        print(f"  [WARN] No valid records in {path}")
        return None

    rows = []
    for ts in sorted(records.keys()):
        r = records[ts]
        cyc   = r.get('cycles', 0)
        instr = r.get('instructions', 0)
        s_mem = r.get('cycle_activity.stalls_mem_any', 0)
        s_tot = r.get('cycle_activity.stalls_total', 0)
        s_nex = r.get('cycle_activity.cycles_no_execute', 0)

        if cyc == 0 or instr == 0:
            continue

        ipc        = instr / cyc
        cpi        = cyc   / instr
        stall_mem  = s_mem / cyc
        stall_tot  = s_tot / cyc

        rows.append({
            'timestamp':        ts,
            'cycles':           cyc,
            'instructions':     instr,
            'ipc':              ipc,
            'cpi':              cpi,
            'stalls_mem_any':   s_mem,
            'stalls_total':     s_tot,
            'cycles_no_execute':s_nex,
            'stall_rate_mem':   stall_mem,
            'stall_rate_total': stall_tot,
        })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    # Normalize timestamp to start at 0
    df['t'] = df['timestamp'] - df['timestamp'].min()
    print(f"  [OK] {os.path.basename(path)}: "
          f"{len(df)} samples  "
          f"IPC_mean={df['ipc'].mean():.3f}  "
          f"stall_mem_mean={df['stall_rate_mem'].mean()*100:.1f}%")
    return df


def smooth(series, window=5):
    return series.rolling(window, center=True, min_periods=1).median()


def plot(data):
    """
    Produces two figures:
      Fig 1 — Random pattern: N4 vs N16
      Fig 2 — Sequential pattern: N4 vs N16 (if data available)
    """
    os.makedirs("analysis", exist_ok=True)

    plot_groups = []
    if 'N4 Random' in data or 'N16 Random' in data:
        plot_groups.append(('Random', 'N4 Random', 'N16 Random'))
    if 'N4 Seq' in data or 'N16 Seq' in data:
        plot_groups.append(('Sequential', 'N4 Seq', 'N16 Seq'))

    metrics = [
        ('ipc',           'IPC (Instructions Per Cycle)',
         'Higher = better\nLower = CPU stalling'),
        ('stall_rate_mem','Memory Stall Rate\n(stalls_mem_any / cycles)',
         'Higher = more time stalling on memory\n0 = no stall'),
        ('cpi',           'CPI (Cycles Per Instruction)',
         'Lower = better\nHigher = CPU waiting for memory'),
    ]

    n_cols = len(plot_groups)
    fig, axes = plt.subplots(3, n_cols, figsize=(7 * n_cols, 12))
    if n_cols == 1:
        axes = axes.reshape(3, 1)

    fig.suptitle(
        "CPU Stall Analysis — Temporal Evolution\n"
        "System-wide measurement (perf stat -a)  |  1s interval",
        fontsize=13, fontweight='bold'
    )

    for col, (pat_label, key_n4, key_n16) in enumerate(plot_groups):
        df_n4  = data.get(key_n4)
        df_n16 = data.get(key_n16)

        for row, (metric, ylabel, note) in enumerate(metrics):
            ax = axes[row][col]

            for df, key, ls, lw in [
                (df_n4,  key_n4,  '-',  2.2),
                (df_n16, key_n16, '--', 2.2),
            ]:
                if df is None or metric not in df.columns:
                    continue

                color = COLORS[key]
                s     = smooth(df[metric])
                mean  = s.mean()
                label = f"{key}  (mean={mean:.3f})"

                ax.plot(df['t'], s,
                        color=color, linestyle=ls, linewidth=lw,
                        label=label, alpha=0.85)
                ax.axhline(mean,
                           color=color, linestyle=':', linewidth=1.2,
                           alpha=0.5)

            if row == 0:
                ax.set_title(f"{pat_label} access pattern",
                             fontsize=11, fontweight='bold')

            ax.set_xlabel("Time (s)", fontsize=9)
            ax.set_ylabel(ylabel, fontsize=9)
            ax.legend(fontsize=8, loc='upper right')
            ax.grid(True, alpha=0.25)
            ax.set_ylim(bottom=0)
            ax.text(0.02, 0.03, note,
                    transform=ax.transAxes, fontsize=7,
                    color='gray', va='bottom',
                    bbox=dict(boxstyle='round',
                              facecolor='white', alpha=0.5))

    plt.tight_layout()
    out = "analysis/stalls_timeline.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    print(f"\n[OK] Plot saved: {out}")
    plt.close()


def print_summary(data):
    print(f"\n{'='*70}")
    print("  SUMMARY — Mean values over captured window")
    print(f"{'='*70}")
    print(f"  {'Scenario':<15} {'IPC':>6} {'CPI':>6} "
          f"{'Stall_mem%':>11} {'Stall_tot%':>11}")
    print("  " + "-"*55)
    for label, df in data.items():
        if df is None:
            continue
        ipc  = df['ipc'].mean()
        cpi  = df['cpi'].mean()
        sm   = df['stall_rate_mem'].mean()   * 100
        st   = df['stall_rate_total'].mean() * 100
        print(f"  {label:<15} {ipc:>6.3f} {cpi:>6.3f} "
              f"{sm:>10.1f}% {st:>10.1f}%")

    # Delta N4 vs N16
    print(f"\n  {'Comparison':<20} {'ΔIPC':>8} {'ΔStall_mem%':>12}")
    print("  " + "-"*45)
    for pat in ['Random', 'Seq']:
        k4  = f'N4 {pat}'
        k16 = f'N16 {pat}'
        if k4 in data and k16 in data and data[k4] is not None and data[k16] is not None:
            d_ipc   = data[k16]['ipc'].mean()            - data[k4]['ipc'].mean()
            d_stall = data[k16]['stall_rate_mem'].mean() - data[k4]['stall_rate_mem'].mean()
            print(f"  N4→N16 {pat:<13} {d_ipc:>+8.3f} {d_stall*100:>+11.1f}%")


if __name__ == "__main__":
    print("=== Stall Timeline Analysis ===\n")
    print("Loading files...")

    data = {}
    for label, fname in FILES.items():
        path = os.path.join(RESULTS_DIR, fname)
        data[label] = parse_perf_file(path)

    available = {k: v for k, v in data.items() if v is not None}
    if not available:
        print("[ERROR] No data loaded.")
    else:
        print_summary(available)
        plot(available)