import matplotlib.pyplot as plt
import numpy as np
import os
import glob
import csv

# --- 1. Global Parameters ---
scenarios = ['baseline', 'extreme', 'cross-numa', 'extreme-cross']
labels = ['Baseline', 'Extreme', 'Cross-NUMA', 'Ex-Cross']
x = np.arange(len(scenarios))
width = 0.35

# --- 2. Aggregation Function ---
def aggregate_performance_data(base_path, folder_suffix, pattern_file, search_pattern, size_kb):
    aggregated_bw = []
    aggregated_lat_avg = []
    aggregated_lat_max = []

    for scen in scenarios:
        # e.g., base_path/baseline-*-time/*/memory_benchmark_seq_time.csv
        path_pattern = os.path.join(base_path, f"{scen}-*-{folder_suffix}", "*", pattern_file)
        pod_files = glob.glob(path_pattern)
        
        total_bw = 0
        sum_lat = 0
        max_lat_absolute = 0
        valid_pods = 0

        for file in pod_files:
            with open(file, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) > 2 and row[0] == search_pattern and row[1] == str(size_kb):
                        total_bw += float(row[2])
                        sum_lat += float(row[3])
                        if float(row[5]) > max_lat_absolute:
                            max_lat_absolute = float(row[5])
                        valid_pods += 1
                        break
        
        if valid_pods > 0:
            #aggregated_bw.append(total_bw / (1024**3) if 'seq' in search_pattern else total_bw) 
            aggregated_bw.append(total_bw)
            aggregated_lat_avg.append(sum_lat / valid_pods)
            aggregated_lat_max.append(max_lat_absolute)
        else:
            aggregated_bw.append(0)
            aggregated_lat_avg.append(0)
            aggregated_lat_max.append(0)

    return aggregated_bw, aggregated_lat_avg, aggregated_lat_max

# --- 3. Plotting Function ---
def create_perf_figures(base_dir, folder_suffix, seq_csv, rand_csv, title_prefix, output_filename):
    print(f"Generating aggregated plots for: {title_prefix}...")
    
    bw_seq, _, _ = aggregate_performance_data(base_dir, folder_suffix, seq_csv, "sequential_read", 1048576)
    _, lat_avg_rand, lat_max_rand = aggregate_performance_data(base_dir, folder_suffix, rand_csv, "random_read", 1048576)

    # Check if data was found
    if np.sum(bw_seq) == 0 and np.sum(lat_avg_rand) == 0:
        print(f"  -> WARNING: No data found for {title_prefix}. Check your paths.")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Plot 1: Cumulative Bandwidth
    bars = ax1.bar(labels, bw_seq, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'], edgecolor='black')
    ax1.set_ylabel('Total Bandwidth (GB/s)', fontweight='bold')
    ax1.set_title(f'[{title_prefix}] Total System Throughput (Seq Read)', fontsize=13)
    ax1.grid(axis='y', linestyle='--', alpha=0.7)

    for bar in bars:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + (max(bw_seq)*0.02), f"{yval:.1f}", ha='center', va='bottom', fontsize=11)

    # Plot 2: Latency
    ax2.bar(x - width/2, lat_avg_rand, width, label='Average Latency', color='lightblue', edgecolor='black')
    ax2.bar(x + width/2, lat_max_rand, width, label='Worst Latency (Max)', color='salmon', edgecolor='black', hatch='//')

    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.set_ylabel('Response Time (nanoseconds)', fontweight='bold')
    ax2.set_title(f'[{title_prefix}] QoS Degradation (Random Read)', fontsize=13)
    ax2.legend()
    ax2.grid(axis='y', linestyle='--', alpha=0.7)

    for i in range(len(x)):
        ax2.text(x[i] - width/2, lat_avg_rand[i] + (max(lat_max_rand)*0.02), str(int(lat_avg_rand[i])), ha='center', va='bottom', fontsize=9)
        ax2.text(x[i] + width/2, lat_max_rand[i] + (max(lat_max_rand)*0.02), str(int(lat_max_rand[i])), ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"  -> Successfully saved: {output_filename}")

# --- 4. Execution ---
# Mode TIME-BOUND
create_perf_figures(
    base_dir="../results/RESULTS_TIME",
    folder_suffix="time",
    seq_csv="memory_benchmark_seq_time.csv",
    rand_csv="memory_benchmark_rand_time.csv",
    title_prefix="TIME-BOUND",
    output_filename="../analysis/perf_aggregated_time_plot.png"
)

# Mode WORK-BOUND
create_perf_figures(
    base_dir="../results/RESULTS_WORK",
    folder_suffix="work",
    seq_csv="memory_benchmark_seq_work.csv",
    rand_csv="memory_benchmark_rand_work.csv",
    title_prefix="WORK-BOUND",
    output_filename="../analysis/perf_aggregated_work_plot.png"
)