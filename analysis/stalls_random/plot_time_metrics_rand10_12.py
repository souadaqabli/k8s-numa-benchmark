#!/usr/bin/env python3
"""
plot_time_metrics_v2.py

Parses time_metrics.txt files from extreme-rand-N10 and N12.
Merges both runs per scenario into a single boxplot.
Clean boxplots without individual points.
"""

import os
import re
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.transforms as mtransforms

DIAG_DIR = os.path.expanduser("~/sdn2_remote_data/diagnostics")

# Merge runs: both N10 and N10-2 become "Extreme Random N10"
SCENARIOS = {
    "Extreme Random\nN10": ["extreme-rand-N10", "extreme-rand-N10-2"],
    "Extreme Random\nN12": ["extreme-rand-N12", "extreme-rand-N12-2"],
}

METRIC_PATTERNS = {
    'user_time':        (r'User time \(seconds\):\s+([\d.]+)',        float),
    'system_time':      (r'System time \(seconds\):\s+([\d.]+)',      float),
    'wall_clock':       (r'Elapsed.*?(\d+):(\d+\.\d+)',              'time'),
    'major_faults':     (r'Major.*page faults:\s+(\d+)',             int),
    'minor_faults':     (r'Minor.*page faults:\s+(\d+)',             int),
    'invol_ctx_switch': (r'Involuntary context switches:\s+(\d+)',   int),
}


def parse_time_metrics(filepath):
    metrics = {}
    with open(filepath) as f:
        content = f.read()
    for key, (pattern, converter) in METRIC_PATTERNS.items():
        m = re.search(pattern, content)
        if m:
            if converter == 'time':
                metrics[key] = int(m.group(1)) * 60 + float(m.group(2))
            else:
                metrics[key] = converter(m.group(1))
    return metrics


def load_data():
    records = []
    for label, folders in SCENARIOS.items():
        for folder in folders:
            path = os.path.join(DIAG_DIR, folder)
            if not os.path.exists(path):
                continue
            files = glob.glob(os.path.join(path, "*", "time_metrics.txt"))
            for f in files:
                metrics = parse_time_metrics(f)
                metrics['scenario'] = label
                records.append(metrics)
        n = sum(1 for r in records if r['scenario'] == label)
        print(f"  {label.replace(chr(10), ' ')}: {n} pods (merged runs)")
    return pd.DataFrame(records)


def plot(df):
    os.makedirs("analysis", exist_ok=True)

    scenarios = list(SCENARIOS.keys())
    colors = ['#2471a3', '#e74c3c']

    metrics_to_plot = [
        ('user_time',        'User Time (s)',                'CPU time spent computing'),
        ('system_time',      'System Time (s)',              'Kernel time (page faults, memory mgmt)'),
        ('major_faults',     'Major Page Faults',            'Pages fetched from disk — high = memory pressure'),
        ('minor_faults',     'Minor Page Faults',            'Pages reclaimed — high = allocation churn'),
        ('invol_ctx_switch', 'Involuntary Context Switches', 'OS preemptions — high = CPU contention'),
        ('wall_clock',       'Wall Clock Time (s)',          'Total elapsed time per pod'),
    ]

    fig = plt.figure(figsize=(14, 12))
    fig.suptitle(
        "Per-Pod Infrastructure Metrics — Extreme Random N10 vs N12\n"
        "Boxplot = merged runs  |  Box = Q1–Q3  |  Line = median",
        fontsize=13, fontweight='bold'
    )
    gs = gridspec.GridSpec(3, 2, hspace=0.45, wspace=0.35)

    for idx, (metric, ylabel, note) in enumerate(metrics_to_plot):
        row, col = divmod(idx, 2)
        ax = fig.add_subplot(gs[row, col])

        if metric not in df.columns:
            ax.text(0.5, 0.5, f"No data", transform=ax.transAxes, ha='center')
            continue

        data_list = []
        for scen in scenarios:
            vals = df[df['scenario'] == scen][metric].dropna().values
            data_list.append(vals)

        bp = ax.boxplot(
            data_list,
            positions=range(1, len(scenarios) + 1),
            widths=0.5,
            patch_artist=True,
            showfliers=True,
            medianprops=dict(color='black', linewidth=2.5),
            whiskerprops=dict(linewidth=1.5),
            capprops=dict(linewidth=1.5),
            boxprops=dict(linewidth=1.5),
            flierprops=dict(marker='o', markersize=5, alpha=0.6, zorder=2),
        )

        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.55)

        # Zoom the y-axis to the box+whiskers instead of forcing a 0 baseline.
        # A 0 baseline is only useful when the data floor is already close to
        # 0 relative to its spread — otherwise it crushes a tight box into an
        # unreadable sliver (this is what happened to user_time, wall_clock
        # and minor_faults before).
        cap_ys = [c.get_ydata()[0] for c in bp['caps']]
        if cap_ys:
            w_lo, w_hi = min(cap_ys), max(cap_ys)
            span = w_hi - w_lo if w_hi > w_lo else max(w_hi * 0.1, 1)
            pad = span * 0.25
            ylo = max(0, w_lo - pad) if w_lo < 0.4 * w_hi else w_lo - pad
            yhi = w_hi + pad * 2.2  # extra headroom reserved for the annotation
            ax.set_ylim(ylo, yhi)

            # extreme fliers beyond the zoomed range get clipped — disclose it
            n_above = sum(1 for vals in data_list for v in vals if v > yhi)
            n_below = sum(1 for vals in data_list for v in vals if v < ylo)
            if n_above or n_below:
                bits = []
                if n_above:
                    bits.append(f"{n_above} above")
                if n_below:
                    bits.append(f"{n_below} below")
                ax.text(0.02, 0.02, f"({', '.join(bits)} view range)",
                        transform=ax.transAxes, fontsize=6.5, color='dimgray',
                        style='italic', ha='left', va='bottom')

        # Annotate median/n — x in data coords, y in axes-fraction coords so
        # the box never collides with the title regardless of the y-scale
        trans = mtransforms.blended_transform_factory(ax.transData, ax.transAxes)
        for i, (vals, scen) in enumerate(zip(data_list, scenarios), start=1):
            if len(vals) == 0:
                continue
            med = np.median(vals)
            n_runs = len(SCENARIOS[scen])
            ax.text(i, 0.94, f"{n_runs} runs  med={med:.1f}",
                    transform=trans, ha='center', va='top', fontsize=8,
                    bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7, pad=0.25))

        # Delta annotation between N10 and N12
        if len(data_list) == 2 and len(data_list[0]) > 0 and len(data_list[1]) > 0:
            med_n10 = np.median(data_list[0])
            med_n12 = np.median(data_list[1])
            if med_n10 > 0:
                ratio = med_n12 / med_n10
                delta_color = 'darkred' if ratio > 1.2 else 'darkgreen'
                ax.text(0.97, 0.03,
                        f"N12/N10 = ×{ratio:.2f}",
                        transform=ax.transAxes,
                        ha='right', va='bottom', fontsize=9,
                        color=delta_color, fontweight='bold',
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

        ax.set_xticks(range(1, len(scenarios) + 1))
        ax.set_xticklabels(scenarios, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(note, fontsize=8, color='gray', style='italic', loc='left', pad=4)
        ax.grid(axis='y', alpha=0.3)

    plt.savefig("analysis/time_metrics_n10_vs_n12.png", dpi=150, bbox_inches='tight')
    print(f"\n[OK] Plot saved: analysis/time_metrics_n10_vs_n12.png")
    plt.close()

    # Summary
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    for scen in scenarios:
        sub = df[df['scenario'] == scen]
        clean = scen.replace('\n', ' ')
        print(f"\n  {clean} ({len(sub)} pods):")
        for m, ylabel, _ in metrics_to_plot:
            if m in sub.columns:
                vals = sub[m].dropna()
                print(f"    {m:<22}: median={vals.median():>10.1f}  "
                      f"total={vals.sum():>12.0f}")


if __name__ == "__main__":
    print("=== time -v Metrics: N10 vs N12 ===\n")
    df = load_data()
    if df.empty:
        print("[ERROR] No data loaded.")
    else:
        plot(df)