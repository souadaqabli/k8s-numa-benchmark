import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import csv
import os

# --- 1. Global Parameters ---
# On ne garde QUE les scénarios natifs
scenarios = ['Native', 'Native-Overload', 'Native-Asym']
x = np.arange(len(scenarios))
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
comp_labels = ['PKG 0', 'PKG 1', 'DRAM 0', 'DRAM 1']

# --- 2. Dynamic Instructions Reading Function ---
def load_instructions_data(csv_path):
    inst_dict = {}
    if os.path.exists(csv_path):
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f, fieldnames=['scenario', 'total_instructions'])
            for row in reader:
                try:
                    scenario_name = row['scenario'].strip().lower()
                    inst_dict[scenario_name] = float(row['total_instructions'])
                except ValueError:
                    continue # Ignore malformed rows
        print(f"[OK] Fichier d'instructions chargé : {len(inst_dict)} scénarios trouvés.")
    else:
        print(f"[ERROR] Fichier d'instructions introuvable : {csv_path}")
    return inst_dict

# --- 3. Smart Extraction Function (Only Natives) ---
def load_global_rapl_data(csv_path, inst_dict):
    data_store = {'work': {}}
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] Le fichier {csv_path} est introuvable.")
        return None

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            # Ignore header or empty rows
            if not row or row[0].strip().lower() == 'scenario' or row[0].strip().lower() == 'pattern':
                continue
            
            ligne_complete = " ".join(row).lower()
            
            # ==========================================
            # CASE 1: NATIVE-ASYM FORMAT (8 ou 9 columns)
            # ==========================================
            if 'native-asym' in ligne_complete:
                mode = 'work'
                pattern = 'seq' if 'seq' in ligne_complete else 'rand'
                scen = 'Native-Asym'
                instructions = inst_dict.get(f"native-asym-{pattern}")
                
                try:
                    if len(row) >= 9:
                        time_val = float(row[3])
                        pkg0_j = float(row[5]) / 1_000_000
                        pkg1_j = float(row[6]) / 1_000_000
                        dram0_j = float(row[7]) / 1_000_000
                        dram1_j = float(row[8]) / 1_000_000
                    else:
                        time_val = float(row[2])
                        pkg0_j = float(row[4]) / 1_000_000
                        pkg1_j = float(row[5]) / 1_000_000
                        dram0_j = float(row[6]) / 1_000_000
                        dram1_j = float(row[7]) / 1_000_000
                except Exception as e:
                    continue

            # ==========================================
            # CASE 2: CLASSIC NATIVE FORMAT (N4 et N16)
            # ==========================================
            elif 'native' in ligne_complete:
                mode = 'work'
                pattern = 'seq' if 'seq' in ligne_complete else 'rand'

                if 'n16' in ligne_complete:
                    scen = 'Native-Overload'
                    instructions = inst_dict.get(f"native-overload-{pattern}")
                elif 'n4' in ligne_complete:
                    scen = 'Native'
                    instructions = inst_dict.get(f"native-{pattern}", inst_dict.get("native"))
                else:
                    continue # On ignore N20, N24, etc.
                
                try:
                    time_val = float(row[3])
                    pkg0_j = float(row[5]) / 1_000_000
                    pkg1_j = float(row[6]) / 1_000_000
                    dram0_j = float(row[7]) / 1_000_000
                    dram1_j = float(row[8]) / 1_000_000
                except Exception as e:
                    continue
            # On ignore complètement les lignes "baseline", "extreme", etc.
            else:
                continue

            # --- HARDWARE EFFICIENCY CALCULATION (nJ / instruction) ---
            if time_val > 0:
                if instructions and instructions > 0:
                    val_pkg0 = (pkg0_j / instructions) * 1_000_000_000
                    val_pkg1 = (pkg1_j / instructions) * 1_000_000_000
                    val_dram0 = (dram0_j / instructions) * 1_000_000_000
                    val_dram1 = (dram1_j / instructions) * 1_000_000_000
                else:
                    print(f"[Warning] Instructions manquantes pour '{scen}-{pattern}'. Efficacité mise à 0.")
                    val_pkg0 = val_pkg1 = val_dram0 = val_dram1 = 0.0
            else:
                val_pkg0 = val_pkg1 = val_dram0 = val_dram1 = 0.0
            
            data_store[mode][f"{scen}-{pattern}"] = {
                'time': time_val,
                'metric': [val_pkg0, val_pkg1, val_dram0, val_dram1]
            }

    def extract_arrays(mode_dict):
        time_seq, time_rand = [], []
        metric_seq, metric_rand = [], []
        
        for s in scenarios:
            if f"{s}-seq" in mode_dict:
                time_seq.append(mode_dict[f"{s}-seq"]['time'])
                metric_seq.append(mode_dict[f"{s}-seq"]['metric'])
            else:
                time_seq.append(0); metric_seq.append([0,0,0,0])
                
            if f"{s}-rand" in mode_dict:
                time_rand.append(mode_dict[f"{s}-rand"]['time'])
                metric_rand.append(mode_dict[f"{s}-rand"]['metric'])
            else:
                time_rand.append(0); metric_rand.append([0,0,0,0])
                
        return np.array(time_seq), np.array(time_rand), np.array(metric_seq), np.array(metric_rand)

    return extract_arrays(data_store['work'])

# --- 4. Plotting Function ---
def create_figure(time_seq, time_rand, metric_seq, metric_rand, title_prefix, filename):
    if np.sum(time_seq) == 0 and np.sum(time_rand) == 0:
        print("[Erreur] Aucune donnée à tracer.")
        return

    # Taille plus compacte car nous n'avons que 3 barres
    fig, axs = plt.subplots(2, 2, figsize=(14, 12))
    ax_seq_time, ax_seq_eff = axs[0, 0], axs[0, 1]
    ax_rand_time, ax_rand_eff = axs[1, 0], axs[1, 1]
    
    # Barre un peu plus large pour occuper l'espace
    width_bar = 0.5 
    x_indices = np.arange(len(scenarios))
    
    # Noms d'affichage plus descriptifs pour les 3 barres
    display_labels = ['Native\n(4 Pods)', 'Overload\n(16 Pods)', 'Asymétrique\n(Heavy/Light)']

    # ==========================================
    # ROW 1: SEQUENTIAL
    # ==========================================
    
    # Plot 1.1: Sequential Time (Left)
    ax_seq_time.bar(x_indices, time_seq, width_bar, color='lightblue', edgecolor='black')
    ax_seq_time.set_xticks(x_indices)
    ax_seq_time.set_xticklabels(display_labels, rotation=0, fontsize=11)
    ax_seq_time.set_ylabel('Temps d\'exécution (secondes)', fontweight='bold')
    ax_seq_time.set_title(f'{title_prefix} - TEMPS SÉQUENTIEL', fontsize=12, fontweight='bold')
    ax_seq_time.grid(axis='y', linestyle='--', alpha=0.7)
    
    for i in range(len(x_indices)):
        val = time_seq[i]
        if val > 0:
            ax_seq_time.text(x_indices[i], val + (np.max(time_seq)*0.02), f"{int(val)}s", ha='center', va='bottom', fontsize=11, fontweight='bold')

    # Plot 1.2: Sequential Efficiency (Right)
    bottom_seq = np.zeros(len(x_indices))
    for i in range(4):
        ax_seq_eff.bar(x_indices, metric_seq[:, i], width_bar, bottom=bottom_seq, color=colors[i], edgecolor='black')
        bottom_seq += metric_seq[:, i]
        
    ax_seq_eff.set_xticks(x_indices)
    ax_seq_eff.set_xticklabels(display_labels, rotation=0, fontsize=11)
    ax_seq_eff.set_ylabel('Coût par Instruction (nJ/inst)', fontweight='bold')
    ax_seq_eff.set_title(f'{title_prefix} - EFFICACITÉ SÉQUENTIELLE', fontsize=12, fontweight='bold')
    ax_seq_eff.grid(axis='y', linestyle='--', alpha=0.7)
    
    max_y_seq = np.max(bottom_seq) if np.max(bottom_seq) > 0 else 1
    for i in range(len(x_indices)):
        if bottom_seq[i] > 0:
            val_seq = f"{bottom_seq[i]:.1f}"
            ax_seq_eff.text(x_indices[i], bottom_seq[i] + (max_y_seq*0.02), val_seq, ha='center', va='bottom', fontsize=11, fontweight='bold')

    # ==========================================
    # ROW 2: RANDOM
    # ==========================================
    
    # Plot 2.1: Random Time (Left)
    ax_rand_time.bar(x_indices, time_rand, width_bar, color='salmon', edgecolor='black', hatch='//')
    ax_rand_time.set_xticks(x_indices)
    ax_rand_time.set_xticklabels(display_labels, rotation=0, fontsize=11)
    ax_rand_time.set_ylabel('Temps d\'exécution (secondes)', fontweight='bold')
    ax_rand_time.set_title(f'{title_prefix} - TEMPS ALÉATOIRE', fontsize=12, fontweight='bold')
    ax_rand_time.grid(axis='y', linestyle='--', alpha=0.7)
    
    for i in range(len(x_indices)):
        val = time_rand[i]
        if val > 0:
            ax_rand_time.text(x_indices[i], val + (np.max(time_rand)*0.02), f"{int(val)}s", ha='center', va='bottom', fontsize=11, fontweight='bold')

    # Plot 2.2: Random Efficiency (Right)
    bottom_rand = np.zeros(len(x_indices))
    for i in range(4):
        ax_rand_eff.bar(x_indices, metric_rand[:, i], width_bar, bottom=bottom_rand, color=colors[i], edgecolor='black', hatch='//')
        bottom_rand += metric_rand[:, i]
        
    ax_rand_eff.set_xticks(x_indices)
    ax_rand_eff.set_xticklabels(display_labels, rotation=0, fontsize=11)
    ax_rand_eff.set_ylabel('Coût par Instruction (nJ/inst)', fontweight='bold')
    ax_rand_eff.set_title(f'{title_prefix} - EFFICACITÉ ALÉATOIRE', fontsize=12, fontweight='bold')
    ax_rand_eff.grid(axis='y', linestyle='--', alpha=0.7)
    
    max_y_rand = np.max(bottom_rand) if np.max(bottom_rand) > 0 else 1
    for i in range(len(x_indices)):
        if bottom_rand[i] > 0:
            val_rand = f"{bottom_rand[i]:.1f}"
            ax_rand_eff.text(x_indices[i], bottom_rand[i] + (max_y_rand*0.02), val_rand, ha='center', va='bottom', fontsize=11, fontweight='bold')

    # ==========================================
    # Global Legend
    # ==========================================
    legend_elements = [mpatches.Patch(facecolor=colors[i], edgecolor='black', label=comp_labels[i]) for i in range(4)]
    legend_elements.append(mpatches.Patch(facecolor='lightblue', edgecolor='black', label='Temps (Séquentiel)'))
    legend_elements.append(mpatches.Patch(facecolor='salmon', edgecolor='black', hatch='//', label='Temps (Aléatoire)'))
    
    fig.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, 0.98), ncol=6, fontsize=11)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    
    os.makedirs("analysis", exist_ok=True)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"[OK] Graphique généré avec succès : {filename}")
    plt.close()

# --- 5. Main Execution ---
global_path = "results/RAPL/rapl_global_results_utiles.csv"
instructions_path = "total_instructions_work.csv"

print("=== Génération de la comparaison Kubernetes Native ===")
inst_dict = load_instructions_data(instructions_path)

data_work = load_global_rapl_data(global_path, inst_dict)

if data_work:
    wb_time_seq, wb_time_rand, wb_metric_seq, wb_metric_rand = data_work
    create_figure(wb_time_seq, wb_time_rand, wb_metric_seq, wb_metric_rand, 
                  "Kubernetes Natives", "analysis/native_comparison_plot.png")