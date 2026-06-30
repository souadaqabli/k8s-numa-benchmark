#!/usr/bin/env python3
"""
Generates NUMA placement heatmaps by parsing numastat output files.
Reads from:
  - ../sdn2_remote_data/numastat/numastat_hetero_all_seq.txt
  - ../sdn2_remote_data/numastat/numastat_hetero_all_rand.txt
  - ../sdn2_remote_data/numastat/numastat_hetero_heavy_only_seq.txt
  - ../sdn2_remote_data/numastat/numastat_hetero_heavy_only_rand.txt
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import re
import os


def parse_numastat_file(filepath):
    """
    Parse a numastat -p output file.
    Returns a list of dicts: [{'pid': int, 'name': str, 'node0': float, 'node1': float}, ...]
    Only keeps python3 processes (skips perf processes).
    """
    pods = []
    if not os.path.exists(filepath):
        print("[ERROR] File not found: %s" % filepath)
        return pods

    with open(filepath) as f:
        lines = f.readlines()

    in_table = False
    for line in lines:
        line = line.strip()

        # Detect start of per-process table
        if line.startswith('PID') and 'Node 0' in line:
            in_table = True
            continue

        # Skip separator lines
        if line.startswith('---'):
            continue

        # Skip Total line
        if line.startswith('Total'):
            in_table = False
            continue

        if in_table and line:
            # Parse lines like: "28541 (python3)             8.66         4125.74         4132.36"
            match = re.match(
                r'(\d+)\s+\((\w+)\)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',
                line
            )
            if match:
                pid = int(match.group(1))
                name = match.group(2)
                node0 = float(match.group(3))
                node1 = float(match.group(4))

                # Skip perf processes — only keep python3 (the actual workload)
                if name == 'python3':
                    pods.append({
                        'pid': pid,
                        'name': name,
                        'node0': node0,
                        'node1': node1,
                        'total': node0 + node1
                    })

    return pods


def classify_pod(pod):
    """Classify a pod as heavy/light based on memory size, and local/cross based on placement."""
    total = pod['total']
    dominant_pct = max(pod['node0'], pod['node1']) / total * 100 if total > 0 else 0

    # Heavy = buffer ~4GB (total > 3000 MB), Light = buffer ~2GB (total < 3000 MB)
    pod_type = 'heavy' if total > 3000 else 'light'

    # Local = >75% on one node, Cross = split
    if dominant_pct >= 75:
        placement = 'local'
    elif dominant_pct >= 60:
        placement = 'partial'
    else:
        placement = 'cross'

    pod['type'] = pod_type
    pod['placement'] = placement
    pod['dominant_pct'] = dominant_pct
    return pod


def parse_ram_free(filepath):
    """Parse numactl --hardware output from numastat file to get free RAM per node."""
    ram = {'node0_free': 0, 'node1_free': 0, 'node0_size': 15951, 'node1_size': 16111}
    if not os.path.exists(filepath):
        return ram

    with open(filepath) as f:
        for line in f:
            if 'node 0 free' in line:
                match = re.search(r'(\d+)\s+MB', line)
                if match:
                    ram['node0_free'] = int(match.group(1))
            elif 'node 1 free' in line:
                match = re.search(r'(\d+)\s+MB', line)
                if match:
                    ram['node1_free'] = int(match.group(1))
            elif 'node 0 size' in line:
                match = re.search(r'(\d+)\s+MB', line)
                if match:
                    ram['node0_size'] = int(match.group(1))
            elif 'node 1 size' in line:
                match = re.search(r'(\d+)\s+MB', line)
                if match:
                    ram['node1_size'] = int(match.group(1))
    return ram


# ============================================
# VISUALIZATION 1: NUMA Placement Heatmap
# ============================================
def create_placement_heatmap(numastat_dir):
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    for ax, pattern in [(axes[0], 'seq'), (axes[1], 'rand')]:
        filepath = os.path.join(numastat_dir, 'numastat_hetero_all_%s.txt' % pattern)
        pods = parse_numastat_file(filepath)

        if not pods:
            ax.text(0.5, 0.5, 'No data found\n%s' % filepath,
                    ha='center', va='center', transform=ax.transAxes)
            continue

        # Classify each pod
        pods = [classify_pod(p) for p in pods]

        # Sort: heavy first, then light
        pods.sort(key=lambda p: (0 if p['type'] == 'heavy' else 1, -p['total']))

        n = len(pods)
        data = np.zeros((n, 2))
        for i, pod in enumerate(pods):
            total = pod['total']
            data[i, 0] = (pod['node0'] / total) * 100 if total > 0 else 0
            data[i, 1] = (pod['node1'] / total) * 100 if total > 0 else 0

        im = ax.imshow(data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=100)

        ax.set_xticks([0, 1])
        ax.set_xticklabels(['NUMA Node 0\n(Socket 0)', 'NUMA Node 1\n(Socket 1)'],
                           fontsize=11, fontweight='bold')
        ax.set_yticks(range(n))

        # Y labels with classification
        ylabels = []
        for pod in pods:
            label = '%s (PID %d)\n%d MB' % (
                pod['type'].upper(), pod['pid'], int(pod['total']))
            if pod['placement'] == 'cross':
                label += ' — CROSS-NUMA!'
            elif pod['placement'] == 'partial':
                label += ' — partial'
            ylabels.append(label)
        ax.set_yticklabels(ylabels, fontsize=9)

        # Annotate cells with percentage + MB
        for i, pod in enumerate(pods):
            for j in range(2):
                pct = data[i, j]
                mb = pod['node0'] if j == 0 else pod['node1']
                color = 'white' if pct > 70 or pct < 30 else 'black'
                ax.text(j, i, '%.1f%%\n(%d MB)' % (pct, int(mb)),
                        ha='center', va='center', color=color,
                        fontsize=9, fontweight='bold')

        # Highlight cross-NUMA rows with red border
        for i, pod in enumerate(pods):
            if pod['placement'] in ('cross', 'partial'):
                rect = mpatches.FancyBboxPatch(
                    (-0.5, i - 0.5), 2, 1,
                    boxstyle="round,pad=0.02",
                    linewidth=3, edgecolor='red', facecolor='none')
                ax.add_patch(rect)

        title_pattern = 'Sequential' if pattern == 'seq' else 'Random'
        ax.set_title('NUMA Placement — %s\n4 Heavy (4 GB) + 2 Light (2 GB)' % title_pattern,
                     fontsize=12, fontweight='bold')

    cbar = fig.colorbar(im, ax=axes, shrink=0.6, label='Memory on this node (%)')

    legend_elements = [
        mpatches.Patch(facecolor='#D6FFD6', edgecolor='black',
                       label='Local (>75% on one node)'),
        mpatches.Patch(facecolor='#FFD6D6', edgecolor='red', linewidth=2,
                       label='Cross-NUMA (memory split)'),
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=2,
               fontsize=11, bbox_to_anchor=(0.5, -0.02))

    plt.tight_layout()
    outpath = 'analysis/numa_placement_heatmap_hetero.png'
    plt.savefig(outpath, dpi=300, bbox_inches='tight')
    print("[OK] Heatmap saved: %s" % outpath)
    plt.close()


# ============================================
# VISUALIZATION 2: RAM Saturation Chart
# ============================================
def create_ram_saturation_chart(numastat_dir):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, pattern in [(axes[0], 'seq'), (axes[1], 'rand')]:
        heavy_file = os.path.join(numastat_dir, 'numastat_hetero_heavy_only_%s.txt' % pattern)
        all_file = os.path.join(numastat_dir, 'numastat_hetero_all_%s.txt' % pattern)

        ram_before = parse_ram_free(heavy_file)
        ram_after = parse_ram_free(all_file)

        x = np.arange(2)
        width = 0.35

        n0_size = ram_before['node0_size']
        n1_size = ram_before['node1_size']

        before_used = [n0_size - ram_before['node0_free'],
                       n1_size - ram_before['node1_free']]
        before_free = [ram_before['node0_free'], ram_before['node1_free']]

        after_used = [n0_size - ram_after['node0_free'],
                      n1_size - ram_after['node1_free']]
        after_free = [ram_after['node0_free'], ram_after['node1_free']]

        ax.bar(x - width/2, before_used, width, label='Used (heavy only)',
               color='#2E86AB', edgecolor='black')
        ax.bar(x - width/2, before_free, width, bottom=before_used,
               color='#B8E0F0', edgecolor='black', alpha=0.5)

        ax.bar(x + width/2, after_used, width, label='Used (all pods)',
               color='#D62828', edgecolor='black')
        ax.bar(x + width/2, after_free, width, bottom=after_used,
               color='#FFB3B3', edgecolor='black', alpha=0.5)

        # Annotate free MB
        for i in range(2):
            ax.text(i - width/2, before_used[i] + before_free[i]/2,
                    '%d MB\nfree' % before_free[i],
                    ha='center', va='center', fontsize=9, color='#2E86AB',
                    fontweight='bold')
            ax.text(i + width/2, after_used[i] + after_free[i]/2,
                    '%d MB\nfree' % after_free[i],
                    ha='center', va='center', fontsize=9, color='#D62828',
                    fontweight='bold')

        # Danger annotation for the most saturated node
        min_free = min(after_free)
        min_idx = after_free.index(min_free)
        if min_free < 2000:
            ax.annotate('Only %d MB free!\nForces Cross-NUMA' % min_free,
                        xy=(min_idx + width/2, after_used[min_idx]),
                        xytext=(min_idx + 0.5, max(n0_size, n1_size) * 0.75),
                        fontsize=10, color='red', fontweight='bold',
                        arrowprops=dict(arrowstyle='->', color='red', lw=2))

        ax.set_xticks(x)
        ax.set_xticklabels(['NUMA Node 0\n(%d MB total)' % n0_size,
                            'NUMA Node 1\n(%d MB total)' % n1_size],
                           fontsize=11)
        ax.set_ylabel('Memory (MB)', fontweight='bold')
        title_pattern = 'Sequential' if pattern == 'seq' else 'Random'
        ax.set_title('%s — NUMA RAM Before vs After Light Pods' % title_pattern,
                     fontsize=12, fontweight='bold')
        ax.legend(loc='upper left')
        ax.set_ylim(0, max(n0_size, n1_size) * 1.1)

    plt.tight_layout()
    outpath = 'analysis/numa_ram_saturation_hetero.png'
    plt.savefig(outpath, dpi=300, bbox_inches='tight')
    print("[OK] RAM saturation chart saved: %s" % outpath)
    plt.close()


# ============================================
# VISUALIZATION 3: Per-Pod IPC Comparison
# ============================================
def create_individual_ipc_chart(numastat_dir, perf_base_dir):
    """
    Reads IPC from perf CSV files and colors bars by NUMA placement.
    Uses numastat to classify pods as local vs cross-NUMA.
    """
    import csv
    import glob

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    color_map = {'local': '#2CA02C', 'partial': '#FF7F0E', 'cross': '#D62828'}

    for ax, pattern in [(axes[0], 'seq'), (axes[1], 'rand')]:
        # Parse numastat to get placement classification
        numastat_file = os.path.join(numastat_dir, 'numastat_hetero_all_%s.txt' % pattern)
        numa_pods = parse_numastat_file(numastat_file)
        numa_pods = [classify_pod(p) for p in numa_pods]

        # Read IPC from perf CSVs
        all_pod_data = []

        for pod_type in ['heavy', 'light']:
            base = os.path.join(perf_base_dir, 'native-%s-%s' % (pod_type, pattern))
            if not os.path.exists(base):
                continue

            for pod_dir in sorted(os.listdir(base)):
                full_path = os.path.join(base, pod_dir)
                if not os.path.isdir(full_path):
                    continue

                csv_files = glob.glob(full_path + '/**/*.csv', recursive=True)
                pod_inst = 0
                pod_cyc = 0

                for f in csv_files:
                    with open(f) as fh:
                        for row in csv.DictReader(fh):
                            try:
                                c = float(row['cycles'])
                                i = float(row['IPC'])
                                pod_cyc += c
                                pod_inst += c * i
                            except (ValueError, KeyError):
                                continue

                if pod_cyc > 0:
                    ipc = pod_inst / pod_cyc
                    all_pod_data.append({
                        'name': '%s %s' % (pod_type.capitalize(), pod_dir[-5:]),
                        'ipc': ipc,
                        'type': pod_type,
                        'inst': pod_inst,
                        'cycles': pod_cyc,
                    })

        if not all_pod_data:
            ax.text(0.5, 0.5, 'No perf data found', ha='center', va='center',
                    transform=ax.transAxes)
            continue

        # Match perf data with numastat classification
        # Sort numastat pods by total memory (heavy first) to match perf order
        numa_sorted = sorted(numa_pods, key=lambda p: -p['total'])

        # Sort perf pods: heavy first (by type), then by name
        all_pod_data.sort(key=lambda p: (0 if p['type'] == 'heavy' else 1, p['name']))

        # Assign placement from numastat (match by order within type)
        heavy_numa = [p for p in numa_sorted if p['type'] == 'heavy']
        light_numa = [p for p in numa_sorted if p['type'] == 'light']
        heavy_perf = [p for p in all_pod_data if p['type'] == 'heavy']
        light_perf = [p for p in all_pod_data if p['type'] == 'light']

        # Sort both by a metric to try to align them
        # Best heuristic: sort numastat by dominant_pct, perf by IPC
        heavy_numa.sort(key=lambda p: -p['dominant_pct'])
        heavy_perf.sort(key=lambda p: -p['ipc'])
        light_numa.sort(key=lambda p: -p['dominant_pct'])
        light_perf.sort(key=lambda p: -p['ipc'])

        for i, p in enumerate(heavy_perf):
            if i < len(heavy_numa):
                p['placement'] = heavy_numa[i]['placement']
            else:
                p['placement'] = 'local'

        for i, p in enumerate(light_perf):
            if i < len(light_numa):
                p['placement'] = light_numa[i]['placement']
            else:
                p['placement'] = 'local'

        # Merge back and sort by IPC descending
        all_pod_data = heavy_perf + light_perf
        all_pod_data.sort(key=lambda p: -p['ipc'])

        names = [p['name'] for p in all_pod_data]
        ipcs = [p['ipc'] for p in all_pod_data]
        colors = [color_map.get(p['placement'], '#888888') for p in all_pod_data]

        bars = ax.bar(range(len(names)), ipcs, color=colors, edgecolor='black', linewidth=0.8)

        # Annotate IPC values
        for i, pod in enumerate(all_pod_data):
            ax.text(i, pod['ipc'] + max(ipcs) * 0.02, '%.3f' % pod['ipc'],
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
            if pod['placement'] in ('cross', 'partial'):
                ax.text(i, pod['ipc'] / 2, 'CROSS\nNUMA',
                        ha='center', va='center', fontsize=8, color='white',
                        fontweight='bold')

        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=20, fontsize=9, ha='right')
        ax.set_ylabel('IPC (Instructions Per Cycle)', fontweight='bold')
        title_pattern = 'Sequential' if pattern == 'seq' else 'Random'
        ax.set_title('%s — IPC per Pod\n(colored by NUMA placement from numastat)' % title_pattern,
                     fontsize=12, fontweight='bold')
        ax.grid(axis='y', linestyle='--', alpha=0.5)

    legend_elements = [
        mpatches.Patch(color='#2CA02C', label='Local placement'),
        mpatches.Patch(color='#FF7F0E', label='Partial cross-NUMA'),
        mpatches.Patch(color='#D62828', label='Cross-NUMA'),
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=3,
               fontsize=11, bbox_to_anchor=(0.5, -0.02))

    plt.tight_layout()
    outpath = 'analysis/individual_ipc_per_pod_hetero.png'
    plt.savefig(outpath, dpi=300, bbox_inches='tight')
    print("[OK] Individual IPC chart saved: %s" % outpath)
    plt.close()


# ============================================
# MAIN
# ============================================
if __name__ == '__main__':
    os.makedirs('analysis', exist_ok=True)

    numastat_dir = '/home/sdnuser/sdn2_remote_data/numastat'
    perf_dir = '/home/sdnuser/sdn2_remote_data/diagnostics'

    print("=== Parsing numastat files ===")
    for pattern in ['seq', 'rand']:
        filepath = os.path.join(numastat_dir, 'numastat_hetero_all_%s.txt' % pattern)
        pods = parse_numastat_file(filepath)
        pods = [classify_pod(p) for p in pods]
        print("\n%s — %d python3 processes found:" % (pattern.upper(), len(pods)))
        for p in pods:
            print("  PID %5d : %s %-7s | Node0=%7.1f MB  Node1=%7.1f MB  | %.1f%% dominant → %s" % (
                p['pid'], p['type'], '(%d MB)' % int(p['total']),
                p['node0'], p['node1'], p['dominant_pct'], p['placement']))

    print("\n=== Generating visualizations ===")
    create_placement_heatmap(numastat_dir)
    create_ram_saturation_chart(numastat_dir)
    create_individual_ipc_chart(numastat_dir, perf_dir)
    print("\n=== All visualizations generated in analysis/ ===")