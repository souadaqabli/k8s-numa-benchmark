import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import csv
import os

# --- 1. Paramètres Globaux ---
# On ne garde QUE les 3 scénarios natifs
scenarios = ['Native', 'Native-Overload', 'Native-Asym']
x = np.arange(len(scenarios))
width = 0.35
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
comp_labels = ['PKG 0', 'PKG 1', 'DRAM 0', 'DRAM 1']

# --- 2. Fonction d'extraction Intelligente ---
def load_global_rapl_data(csv_path):
    data_store = {'work': {}}
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] Le fichier {csv_path} est introuvable.")
        return None

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].strip().lower() == 'scenario' or row[0].strip().lower() == 'pattern':
                continue
            
            ligne_complete = " ".join(row).lower()
            
            # --- FILTRE : On ignore tout ce qui n'est pas "native" ---
            if 'native' not in ligne_complete:
                continue

            # --- PARSING DU FORMAT NATIVE ---
            mode = 'work'
            pattern = 'seq' if 'seq' in ligne_complete else 'rand'
            
            # Gestion de native-asym (format 8 ou 9 colonnes possible selon tes manips)
            if 'native-asym' in ligne_complete:
                scen = 'Native-Asym'
                try:
                    if len(row) >= 9:
                        time_val = float(row[3])
                        pkg0_uj = float(row[5])
                        pkg1_uj = float(row[6])
                        dram0_uj = float(row[7])
                        dram1_uj = float(row[8])
                    else:
                        time_val = float(row[2])
                        pkg0_uj = float(row[4])
                        pkg1_uj = float(row[5])
                        dram0_uj = float(row[6])
                        dram1_uj = float(row[7])
                except Exception:
                    continue
            
            # Gestion de Native-N4 et Native-N16 (format classique 9 colonnes)
            else:
                if 'n16' in ligne_complete:
                    scen = 'Native-Overload'
                elif 'n4' in ligne_complete:
                    scen = 'Native'
                else:
                    continue # On ignore silencieusement N20, N24, etc.
                
                try:
                    time_val = float(row[3])
                    pkg0_uj = float(row[5])
                    pkg1_uj = float(row[6])
                    dram0_uj = float(row[7])
                    dram1_uj = float(row[8])
                except Exception:
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

    return extract_arrays(data_store['work'])

# --- 3. Dessin des graphiques ---
def create_figure(time_seq, time_rand, power_seq, power_rand, title_prefix, filename):
    if np.sum(time_seq) == 0 and np.sum(time_rand) == 0:
        print(f"[Erreur] Aucune donnée à tracer pour {title_prefix}")
        return

    # Taille réduite pour 3 barres
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    
    # Étiquettes plus explicites pour l'axe X
    display_labels = ['Native\n(4 Pods)', 'Overload\n(16 Pods)', 'Asymétrique\n(Heavy/Light)']
    
    # --- GRAPHE 1 : TEMPS ---
    ax1.bar(x - width/2, time_seq, width, label='Séquentiel', color='lightblue', edgecolor='black')
    ax1.bar(x + width/2, time_rand, width, label='Aléatoire', color='salmon', edgecolor='black', hatch='//')
    ax1.set_xticks(x)
    ax1.set_xticklabels(display_labels, rotation=0, fontsize=11)
    ax1.set_ylabel('Temps d\'exécution (secondes)', fontweight='bold')
    ax1.set_title(f'{title_prefix} - Temps d\'exécution', fontsize=14)
    ax1.grid(axis='y', linestyle='--', alpha=0.7)

    for i in range(len(x)):
        if time_seq[i] > 0:
            ax1.text(x[i] - width/2, time_seq[i] + (max(time_rand)*0.02), str(int(time_seq[i])), ha='center', va='bottom', fontsize=11, fontweight='bold')
        if time_rand[i] > 0:
            ax1.text(x[i] + width/2, time_rand[i] + (max(time_rand)*0.02), str(int(time_rand[i])), ha='center', va='bottom', fontsize=11, fontweight='bold')

    # --- GRAPHE 2 : PUISSANCE (WATTS) ---
    bottom_seq = np.zeros(len(x))
    bottom_rand = np.zeros(len(x))
    for i in range(4):
        ax2.bar(x - width/2, power_seq[:, i], width, bottom=bottom_seq, color=colors[i], edgecolor='black')
        ax2.bar(x + width/2, power_rand[:, i], width, bottom=bottom_rand, color=colors[i], edgecolor='black', hatch='//')
        bottom_seq += power_seq[:, i]
        bottom_rand += power_rand[:, i]
        
    ax2.set_xticks(x)
    ax2.set_xticklabels(display_labels, rotation=0, fontsize=11)
    
    ax2.set_ylabel('Puissance Moyenne (Watts)', fontweight='bold')
    ax2.set_title(f'{title_prefix} - Distribution Électrique', fontsize=14)
    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    
    for i in range(len(x)):
        if bottom_seq[i] > 0:
            ax2.text(x[i] - width/2, bottom_seq[i] + (max(bottom_rand)*0.02), str(int(bottom_seq[i])), ha='center', va='bottom', fontsize=11, fontweight='bold')
        if bottom_rand[i] > 0:
            ax2.text(x[i] + width/2, bottom_rand[i] + (max(bottom_rand)*0.02), str(int(bottom_rand[i])), ha='center', va='bottom', fontsize=11, fontweight='bold')

    # --- LÉGENDE GLOBALE ---
    legend_elements = [mpatches.Patch(facecolor=colors[i], edgecolor='black', label=comp_labels[i]) for i in range(4)]
    legend_elements.append(mpatches.Patch(facecolor='white', edgecolor='black', label='Séquentiel (Plein)'))
    legend_elements.append(mpatches.Patch(facecolor='white', edgecolor='black', hatch='//', label='Aléatoire (Hachuré)'))
    
    # Déplacement de la légende au-dessus du graphique 2 pour un rendu plus propre
    ax2.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.02, 1))

    plt.tight_layout()
    os.makedirs("analysis", exist_ok=True)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"[OK] Graphique généré avec succès : {filename}")
    plt.close()

# --- 4. Main Execution ---
global_path = "results/RAPL/rapl_global_results_utiles.csv"

print("=== Génération de la comparaison de puissance Kubernetes Native ===")
data_work = load_global_rapl_data(global_path)

if data_work:
    wb_time_seq, wb_time_rand, wb_power_seq, wb_power_rand = data_work
    create_figure(wb_time_seq, wb_time_rand, wb_power_seq, wb_power_rand, "Comparaison Kubernetes Natives", "analysis/native_power_comparison_plot.png")