import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import csv
import os

# --- 1. Global Parameters ---
scenarios = ['Baseline', 'Extreme', 'Cross-NUMA', 'Ex-Cross']
x = np.arange(len(scenarios))
width = 0.35
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
comp_labels = ['PKG 0', 'PKG 1', 'DRAM 0', 'DRAM 1']

# --- 2. Smart Extraction Function (Last run wins) ---
def load_global_rapl_data(csv_path):
    # Separate dictionaries for Work and Time
    # The key will be e.g.: "Baseline-seq". If we encounter this key again, it overwrites the old one!
    data_store = {'work': {}, 'time': {}}
    
    if not os.path.exists(csv_path):
        print(f"Error: The file {csv_path} was not found.")
        return None, None

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 8:
                continue
            
            name = row[0].lower() # e.g.: 'baseline-seq-time' or 'extreme-rand-work'
            
            # 1. Global mode detection (Work or Time)
            if 'work' in name:
                mode = 'work'
            elif 'time' in name:
                mode = 'time'
            else:
                continue # Unrecognized line

            # 2. Pattern and scenario detection
            pattern = 'seq' if 'seq' in name else 'rand'
            
            if 'extreme-cross' in name: scen = 'Ex-Cross'
            elif 'cross-numa' in name: scen = 'Cross-NUMA'
            elif 'extreme' in name: scen = 'Extreme'
            elif 'baseline' in name: scen = 'Baseline'
            else: continue
            
            # 3. Extraction (and conversion to Joules)
            time_val = float(row[2])
            pkg0 = float(row[4]) / 1_000_000
            pkg1 = float(row[5]) / 1_000_000
            dram0 = float(row[6]) / 1_000_000
            dram1 = float(row[7]) / 1_000_000
            
            # 4. MAGIC SAVE: Overwrite the old value if it exists
            # This way, only the most recent run (lowest in the CSV) will survive.
            data_store[mode][f"{scen}-{pattern}"] = {
                'time': time_val,
                'ener': [pkg0, pkg1, dram0, dram1]
            }

    # Internal function to transform the dictionary into arrays for plotting
    def extract_arrays(mode_dict):
        time_seq, time_rand = [], []
        ener_seq, ener_rand = [], []
        for s in scenarios:
            # Seq
            if f"{s}-seq" in mode_dict:
                time_seq.append(mode_dict[f"{s}-seq"]['time'])
                ener_seq.append(mode_dict[f"{s}-seq"]['ener'])
            else:
                time_seq.append(0)
                ener_seq.append([0,0,0,0])
            # Rand
            if f"{s}-rand" in mode_dict:
                time_rand.append(mode_dict[f"{s}-rand"]['time'])
                ener_rand.append(mode_dict[f"{s}-rand"]['ener'])
            else:
                time_rand.append(0)
                ener_rand.append([0,0,0,0])
        return np.array(time_seq), np.array(time_rand), np.array(ener_seq), np.array(ener_rand)

    return extract_arrays(data_store['work']), extract_arrays(data_store['time'])

# --- 3. Plotting Function (Totally Unchanged) ---
def create_figure(time_seq, time_rand, ener_seq, ener_rand, title_prefix, filename):
    if np.sum(time_seq) == 0 and np.sum(time_rand) == 0:
        print(f"No data for {title_prefix}")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    ax1.bar(x - width/2, time_seq, width, label='Sequential', color='lightblue', edgecolor='black')
    ax1.bar(x + width/2, time_rand, width, label='Random', color='salmon', edgecolor='black', hatch='//')
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenarios)
    ax1.set_ylabel('Time (seconds)', fontweight='bold')
    ax1.set_title(f'{title_prefix} - Execution Time', fontsize=14)
    ax1.legend()
    ax1.grid(axis='y', linestyle='--', alpha=0.7)

    for i in range(len(x)):
        ax1.text(x[i] - width/2, time_seq[i] + (max(time_rand)*0.02), str(int(time_seq[i])), ha='center', va='bottom', fontsize=10)
        ax1.text(x[i] + width/2, time_rand[i] + (max(time_rand)*0.02), str(int(time_rand[i])), ha='center', va='bottom', fontsize=10)

    bottom_seq = np.zeros(4)
    bottom_rand = np.zeros(4)
    for i in range(4):
        ax2.bar(x - width/2, ener_seq[:, i], width, bottom=bottom_seq, color=colors[i], edgecolor='black')
        ax2.bar(x + width/2, ener_rand[:, i], width, bottom=bottom_rand, color=colors[i], edgecolor='black', hatch='//')
        bottom_seq += ener_seq[:, i]
        bottom_rand += ener_rand[:, i]
        
    ax2.set_xticks(x)
    ax2.set_xticklabels(scenarios)
    ax2.set_ylabel('Energy (Joules)', fontweight='bold')
    ax2.set_title(f'{title_prefix} - Energy Distribution', fontsize=14)
    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    
    for i in range(len(x)):
        ax2.text(x[i] - width/2, bottom_seq[i] + (max(bottom_rand)*0.02), str(int(bottom_seq[i])), ha='center', va='bottom', fontsize=10)
        ax2.text(x[i] + width/2, bottom_rand[i] + (max(bottom_rand)*0.02), str(int(bottom_rand[i])), ha='center', va='bottom', fontsize=10)

    legend_elements = [mpatches.Patch(facecolor=colors[i], edgecolor='black', label=comp_labels[i]) for i in range(4)]
    legend_elements.append(mpatches.Patch(facecolor='white', edgecolor='black', label='Sequential (Solid)'))
    legend_elements.append(mpatches.Patch(facecolor='white', edgecolor='black', hatch='//', label='Random (Hatched)'))
    ax2.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1))

    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"Plot successfully generated: {filename}")
    plt.close()

# --- 4. Main Execution ---
global_path = "../results/RAPL/rapl_global_results.csv" # <-- PUT THE CORRECT PATH HERE

print("Reading global file and filtering recent runs...")
data_work, data_time = load_global_rapl_data(global_path)

if data_work and data_time:
    wb_time_seq, wb_time_rand, wb_ener_seq, wb_ener_rand = data_work
    create_figure(wb_time_seq, wb_time_rand, wb_ener_seq, wb_ener_rand, "WORK-BOUND Mode (10 GB)", "../analysis/work_bound_plot.png")

    tb_time_seq, tb_time_rand, tb_ener_seq, tb_ener_rand = data_time
    create_figure(tb_time_seq, tb_time_rand, tb_ener_seq, tb_ener_rand, "TIME-BOUND Mode (60s)", "../analysis/time_bound_plot.png")