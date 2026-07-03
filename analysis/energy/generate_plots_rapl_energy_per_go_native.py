import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import csv
import os

# --- 1. Paramètres Globaux ---
# Les 4 scénarios de contention NUMA + les 2 scénarios natifs (N4, N16). N6/N20 ignorés pour le moment.
scenarios = ['Baseline', 'Extreme', 'Cross-NUMA', 'Ex-Cross', 'Native', 'Native-Overload']
display_labels = ['Baseline', 'Extreme', 'Cross-NUMA', 'Ex-Cross', 'Native\n(N4)', 'Overload\n(N16)']
x = np.arange(len(scenarios))
width = 0.35
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
comp_labels = ['PKG 0', 'PKG 1', 'DRAM 0', 'DRAM 1']

# --- Calcul du volume de données réellement traité (mode WORK-BOUND) ---
# script_controlled.py boucle sur 6 tailles de buffer x 2 modes (read+write),
# et mem_stress_controlled.py traite ~10 GiB par sous-test (--target-mb 10240).
# => 6 * 2 * 10 = 120 GiB traités PAR POD pour un scénario donné (seq ou rand).
GB_PER_POD = 6 * 2 * 10

# Baseline/Extreme/Cross-NUMA/Ex-Cross et Native (N4) utilisent tous 4 pods en parallèle
# (cf. deployments/controlled/{seq,rand}/*-work.yaml et deployments/scalability/*/N4/native.yaml).
# Native-Overload (N16) est un Job K8s avec parallelism=16.
NUM_PODS = {
    'Baseline': 4, 'Extreme': 4, 'Cross-NUMA': 4, 'Ex-Cross': 4,
    'Native': 4, 'Native-Overload': 16,
}
GB_PROCESSED = {s: NUM_PODS[s] * GB_PER_POD for s in NUM_PODS}

# --- 2. Fonction d'extraction (4 scénarios + native N4/N16) ---
def load_global_rapl_data(csv_path):
    data_store = {'work': {}}

    if not os.path.exists(csv_path):
        print(f"[ERROR] Le fichier {csv_path} est introuvable.")
        return None

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].strip().lower() in ('scenario', 'pattern'):
                continue

            ligne_complete = " ".join(row).lower()

            # ==========================================
            # CAS 1 : FORMAT NATIF (9 colonnes)
            # pattern,N,type,time,colsum,pkg0,pkg1,dram0,dram1
            # ==========================================
            if len(row) >= 9 and 'native' in row[2].strip().lower():
                pattern = row[0].strip().lower()
                cores = row[1].strip().lower()

                if cores == 'n16':
                    scen = 'Native-Overload'
                elif cores == 'n4':
                    scen = 'Native'
                else:
                    continue  # N6, N20, etc. ignorés pour le moment

                try:
                    time_val = float(row[3])
                    pkg0_j = float(row[5]) / 1_000_000
                    pkg1_j = float(row[6]) / 1_000_000
                    dram0_j = float(row[7]) / 1_000_000
                    dram1_j = float(row[8]) / 1_000_000
                except (ValueError, IndexError):
                    continue

            # ==========================================
            # CAS 2 : FORMAT SCÉNARIO (8 colonnes)
            # name,run,time,colsum,pkg0,pkg1,dram0,dram1
            # ==========================================
            elif len(row) >= 8 and 'native' not in row[0].strip().lower():
                name = row[0].strip().lower()

                if 'work' not in name:
                    continue  # Uniquement le mode Work-Bound

                pattern = 'seq' if 'seq' in name else 'rand'

                if 'extreme-cross' in name: scen = 'Ex-Cross'
                elif 'cross-numa' in name: scen = 'Cross-NUMA'
                elif 'extreme' in name: scen = 'Extreme'
                elif 'baseline' in name: scen = 'Baseline'
                else: continue

                try:
                    time_val = float(row[2])
                    # ATTENTION : row[3] (colsum) = pkg0+pkg1 SEULEMENT (bug), on ne l'utilise pas.
                    # Le total réel = pkg0 + pkg1 + dram0 + dram1
                    pkg0_j = float(row[4]) / 1_000_000
                    pkg1_j = float(row[5]) / 1_000_000
                    dram0_j = float(row[6]) / 1_000_000
                    dram1_j = float(row[7]) / 1_000_000
                except (ValueError, IndexError):
                    continue
            else:
                continue

            # --- Normalisation par Go traité (volume système = pods x 120 GiB) ---
            gb = GB_PROCESSED[scen]
            per_go = [pkg0_j / gb, pkg1_j / gb, dram0_j / gb, dram1_j / gb]

            # MAGIC SAVE : la dernière occurrence (run le plus récent) écrase la précédente
            data_store['work'][f"{scen}-{pattern}"] = {
                'time': time_val,
                'ener_per_go': per_go
            }

    def extract_arrays(mode_dict):
        time_seq, time_rand = [], []
        ener_seq, ener_rand = [], []
        for s in scenarios:
            if f"{s}-seq" in mode_dict:
                time_seq.append(mode_dict[f"{s}-seq"]['time'])
                ener_seq.append(mode_dict[f"{s}-seq"]['ener_per_go'])
            else:
                time_seq.append(0)
                ener_seq.append([0, 0, 0, 0])

            if f"{s}-rand" in mode_dict:
                time_rand.append(mode_dict[f"{s}-rand"]['time'])
                ener_rand.append(mode_dict[f"{s}-rand"]['ener_per_go'])
            else:
                time_rand.append(0)
                ener_rand.append([0, 0, 0, 0])
        return np.array(time_seq), np.array(time_rand), np.array(ener_seq), np.array(ener_rand)

    return extract_arrays(data_store['work'])

# --- 3. Fonction de tracé ---
def create_figure(time_seq, time_rand, ener_seq, ener_rand, title_prefix, filename):
    if np.sum(time_seq) == 0 and np.sum(time_rand) == 0:
        print(f"[Erreur] Aucune donnée à tracer pour {title_prefix}")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    ax1.bar(x - width/2, time_seq, width, label='Sequential', color='lightblue', edgecolor='black')
    ax1.bar(x + width/2, time_rand, width, label='Random', color='salmon', edgecolor='black', hatch='//')
    ax1.set_xticks(x)
    ax1.set_xticklabels(display_labels, fontsize=10)
    ax1.set_ylabel('Time (seconds)', fontweight='bold')
    ax1.set_title(f'{title_prefix} - Execution Time', fontsize=14)
    ax1.legend()
    ax1.grid(axis='y', linestyle='--', alpha=0.7)

    for i in range(len(x)):
        if time_seq[i] > 0:
            ax1.text(x[i] - width/2, time_seq[i] + (max(time_rand)*0.02), str(int(time_seq[i])), ha='center', va='bottom', fontsize=9)
        if time_rand[i] > 0:
            ax1.text(x[i] + width/2, time_rand[i] + (max(time_rand)*0.02), str(int(time_rand[i])), ha='center', va='bottom', fontsize=9)

    bottom_seq = np.zeros(len(x))
    bottom_rand = np.zeros(len(x))
    for i in range(4):
        ax2.bar(x - width/2, ener_seq[:, i], width, bottom=bottom_seq, color=colors[i], edgecolor='black')
        ax2.bar(x + width/2, ener_rand[:, i], width, bottom=bottom_rand, color=colors[i], edgecolor='black', hatch='//')
        bottom_seq += ener_seq[:, i]
        bottom_rand += ener_rand[:, i]

    ax2.set_xticks(x)
    ax2.set_xticklabels(display_labels, fontsize=10)
    ax2.set_ylabel('Energy per GB (Joules/GB)', fontweight='bold')
    ax2.set_title(f'{title_prefix} - Energy Distribution per GB', fontsize=14)
    ax2.grid(axis='y', linestyle='--', alpha=0.7)

    for i in range(len(x)):
        if bottom_seq[i] > 0:
            ax2.text(x[i] - width/2, bottom_seq[i] + (max(bottom_rand)*0.02), f"{bottom_seq[i]:.1f}", ha='center', va='bottom', fontsize=9)
        if bottom_rand[i] > 0:
            ax2.text(x[i] + width/2, bottom_rand[i] + (max(bottom_rand)*0.02), f"{bottom_rand[i]:.1f}", ha='center', va='bottom', fontsize=9)

    legend_elements = [mpatches.Patch(facecolor=colors[i], edgecolor='black', label=comp_labels[i]) for i in range(4)]
    legend_elements.append(mpatches.Patch(facecolor='white', edgecolor='black', label='Sequential (Solid)'))
    legend_elements.append(mpatches.Patch(facecolor='white', edgecolor='black', hatch='//', label='Random (Hatched)'))
    ax2.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1))

    plt.tight_layout()
    os.makedirs("analysis", exist_ok=True)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"[OK] Plot successfully generated: {filename}")
    plt.close()

# --- 4. Main Execution ---
global_path = "results/RAPL/rapl_global_results_utiles.csv"

print("=== Génération Energie/Go - 4 scénarios NUMA + Native N4/N16 (Work-Bound) ===")
data_work = load_global_rapl_data(global_path)

if data_work:
    wb_time_seq, wb_time_rand, wb_ener_seq, wb_ener_rand = data_work
    create_figure(wb_time_seq, wb_time_rand, wb_ener_seq, wb_ener_rand,
                  "WORK-BOUND Mode", "analysis/energy_per_go_workbound_native.png")
