import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import csv
import os

# --- 1. Paramètres Globaux ---
scenarios = ['Baseline', 'Extreme', 'Cross-NUMA', 'Ex-Cross', 'Native', 'Native-Overload', 'Native-Asym']
x = np.arange(len(scenarios))
width = 0.35
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
comp_labels = ['PKG 0', 'PKG 1', 'DRAM 0', 'DRAM 1']

# --- 2. Fonction d'extraction Intelligente ---
def load_global_rapl_data(csv_path):
    data_store = {'work': {}, 'time': {}}
    
    if not os.path.exists(csv_path):
        print(f"Error: The file {csv_path} was not found.")
        return None, None

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].strip().lower() == 'scenario' or row[0].strip().lower() == 'pattern':
                continue
            
            ligne_complete = " ".join(row).lower()
            
            # --- CAS 1 : LE FORMAT NATIVE (9 colonnes) ---
            # On vérifie si le mot "native" est présent dans la colonne du scénario (row[2])
            if len(row) >= 9 and 'native' in row[2].strip().lower():
                mode = 'work'
                pattern = row[0].lower().strip()
                cores = row[1].lower().strip()
                scenario_name = row[2].lower().strip()
                
                # CORRECTION ICI : On gère native-asym ET native-n4/n16
                if scenario_name == 'native-asym':
                    scen = 'Native-Asym'
                elif cores == 'n16':
                    scen = 'Native-Overload'
                elif cores == 'n4':
                    scen = 'Native'
                else:
                    continue # On ignore silencieusement les autres configs (N20, etc.)
                
                try:
                    time_val = float(row[3])
                    # L'énergie détaillée commence bien à l'index 5 (après total_uj)
                    pkg0_uj = float(row[5])
                    pkg1_uj = float(row[6])
                    dram0_uj = float(row[7])
                    dram1_uj = float(row[8])
                except ValueError:
                    continue

            # --- CAS 2 : FORMAT INITIAL (8 colonnes) ---
            elif len(row) >= 8 and 'native' not in row:
                name = row[0].lower()
                
                if 'work' in name:
                    mode = 'work'
                elif 'time' in name:
                    mode = 'time'
                else:
                    continue
                    
                pattern = 'seq' if 'seq' in name else 'rand'
                
                if 'extreme-cross' in name: scen = 'Ex-Cross'
                elif 'cross-numa' in name: scen = 'Cross-NUMA'
                elif 'extreme' in name: scen = 'Extreme'
                elif 'baseline' in name: scen = 'Baseline'
                else: continue
                
                try:
                    time_val = float(row[2])
                    pkg0_uj = float(row[4])
                    pkg1_uj = float(row[5])
                    dram0_uj = float(row[6])
                    dram1_uj = float(row[7])
                except ValueError:
                    continue
                
            else:
                continue

            # --- 3. CONVERSION EN WATTS ---
            if time_val > 0:
                pkg0 = (pkg0_uj / 1_000_000) / time_val
                pkg1 = (pkg1_uj / 1_000_000) / time_val
                dram0 = (dram0_uj / 1_000_000) / time_val
                dram1 = (dram1_uj / 1_000_000) / time_val
            else:
                pkg0 = pkg1 = dram0 = dram1 = 0.0
            
            # --- 4. SAUVEGARDE EN ÉCRASANT LES ANCIENNES VALEURS ---
            data_store[mode][f"{scen}-{pattern}"] = {
                'time': time_val,
                'power': [pkg0, pkg1, dram0, dram1]
            }

    def extract_arrays(mode_dict):
        time_seq, time_rand = [], []
        power_seq, power_rand = [], []
        for s in scenarios:
            if f"{s}-seq" in mode_dict:
                time_seq.append(mode_dict[f"{s}-seq"]['time'])
                power_seq.append(mode_dict[f"{s}-seq"]['power'])
            else:
                time_seq.append(0)
                power_seq.append([0,0,0,0])
                
            if f"{s}-rand" in mode_dict:
                time_rand.append(mode_dict[f"{s}-rand"]['time'])
                power_rand.append(mode_dict[f"{s}-rand"]['power'])
            else:
                time_rand.append(0)
                power_rand.append([0,0,0,0])
                
        return np.array(time_seq), np.array(time_rand), np.array(power_seq), np.array(power_rand)

    return extract_arrays(data_store['work']), extract_arrays(data_store['time'])

# --- 3. Dessin des graphiques ---
def create_figure(time_seq, time_rand, power_seq, power_rand, title_prefix, filename):
    if np.sum(time_seq) == 0 and np.sum(time_rand) == 0:
        print(f"No data for {title_prefix}")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # --- GRAPHE 1 : TEMPS ---
    ax1.bar(x - width/2, time_seq, width, label='Sequential', color='lightblue', edgecolor='black')
    ax1.bar(x + width/2, time_rand, width, label='Random', color='salmon', edgecolor='black', hatch='//')
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenarios, rotation=15)
    ax1.set_ylabel('Time (seconds)', fontweight='bold')
    ax1.set_title(f'{title_prefix} - Execution Time', fontsize=14)
    ax1.legend()
    ax1.grid(axis='y', linestyle='--', alpha=0.7)

    for i in range(len(x)):
        if time_seq[i] > 0:
            ax1.text(x[i] - width/2, time_seq[i] + (max(time_rand)*0.02), str(int(time_seq[i])), ha='center', va='bottom', fontsize=10)
        if time_rand[i] > 0:
            ax1.text(x[i] + width/2, time_rand[i] + (max(time_rand)*0.02), str(int(time_rand[i])), ha='center', va='bottom', fontsize=10)

    # --- GRAPHE 2 : PUISSANCE (WATTS) ---
    bottom_seq = np.zeros(len(x))
    bottom_rand = np.zeros(len(x))
    for i in range(4):
        ax2.bar(x - width/2, power_seq[:, i], width, bottom=bottom_seq, color=colors[i], edgecolor='black')
        ax2.bar(x + width/2, power_rand[:, i], width, bottom=bottom_rand, color=colors[i], edgecolor='black', hatch='//')
        bottom_seq += power_seq[:, i]
        bottom_rand += power_rand[:, i]
        
    ax2.set_xticks(x)
    ax2.set_xticklabels(scenarios, rotation=15)
    
    ax2.set_ylabel('Average Power (Watts)', fontweight='bold')
    ax2.set_title(f'{title_prefix} - Power Distribution', fontsize=14)
    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    
    for i in range(len(x)):
        if bottom_seq[i] > 0:
            ax2.text(x[i] - width/2, bottom_seq[i] + (max(bottom_rand)*0.02), str(int(bottom_seq[i])), ha='center', va='bottom', fontsize=10)
        if bottom_rand[i] > 0:
            ax2.text(x[i] + width/2, bottom_rand[i] + (max(bottom_rand)*0.02), str(int(bottom_rand[i])), ha='center', va='bottom', fontsize=10)

    legend_elements = [mpatches.Patch(facecolor=colors[i], edgecolor='black', label=comp_labels[i]) for i in range(4)]
    legend_elements.append(mpatches.Patch(facecolor='white', edgecolor='black', label='Sequential (Solid)'))
    legend_elements.append(mpatches.Patch(facecolor='white', edgecolor='black', hatch='//', label='Random (Hatched)'))
    ax2.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1))

    plt.tight_layout()
    os.makedirs("analysis", exist_ok=True)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"Plot successfully generated: {filename}")
    plt.close()

# --- 4. Main Execution ---
global_path = "results/RAPL/rapl_global_results_utiles.csv"

print("Reading global file and applying power normalization...")
data_work, data_time = load_global_rapl_data(global_path)

if data_work and data_time:
    wb_time_seq, wb_time_rand, wb_power_seq, wb_power_rand = data_work
    create_figure(wb_time_seq, wb_time_rand, wb_power_seq, wb_power_rand, "WORK-BOUND Mode (10 GB)", "analysis/work_bound_power_plot_complete.png")