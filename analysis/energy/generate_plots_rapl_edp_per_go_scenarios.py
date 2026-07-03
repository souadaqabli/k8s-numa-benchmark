import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import csv
import os

# --- 1. Paramètres Globaux ---
# Uniquement les 4 scénarios de contention NUMA (pas de native)
scenarios = ['Baseline', 'Extreme', 'Cross-NUMA', 'Ex-Cross']
x = np.arange(len(scenarios))
width = 0.35
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
comp_labels = ['PKG 0', 'PKG 1', 'DRAM 0', 'DRAM 1']

# --- Calcul du volume de données réellement traité (mode WORK-BOUND) ---
# script_controlled.py boucle sur 6 tailles de buffer x 2 modes (read+write),
# et mem_stress_controlled.py traite ~10 GiB par sous-test (--target-mb 10240).
# => 6 * 2 * 10 = 120 GiB traités PAR POD pour un scénario donné (seq ou rand).
GB_PER_POD = 6 * 2 * 10

# Les 4 scénarios (baseline, extreme, cross-numa, extreme-cross) utilisent tous 4 pods
# en parallèle (cf. deployments/controlled/{seq,rand}/*-work.yaml).
NUM_PODS = 4
GB_PROCESSED = NUM_PODS * GB_PER_POD  # 480 GiB au total pour le système

# --- 2. Fonction d'extraction (Work-Bound uniquement, 4 scénarios uniquement) ---
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

            name = row[0].strip().lower()

            # On ignore les lignes "native" (format à 9 colonnes / autre convention)
            if 'native' in name or len(row) < 8:
                continue

            # Ne garder que le mode Work-Bound
            if 'work' not in name:
                continue

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

            # --- EDP/Go = (Energie x Temps) / Go traité ---
            # EDP (Energy-Delay Product) pénalise à la fois la consommation ET la lenteur.
            edp_per_go = [pkg0_j * time_val / GB_PROCESSED, pkg1_j * time_val / GB_PROCESSED,
                          dram0_j * time_val / GB_PROCESSED, dram1_j * time_val / GB_PROCESSED]

            # MAGIC SAVE : la dernière occurrence (run le plus récent) écrase la précédente
            data_store['work'][f"{scen}-{pattern}"] = {
                'time': time_val,
                'edp_per_go': edp_per_go
            }

    def extract_arrays(mode_dict):
        time_seq, time_rand = [], []
        edp_seq, edp_rand = [], []
        for s in scenarios:
            if f"{s}-seq" in mode_dict:
                time_seq.append(mode_dict[f"{s}-seq"]['time'])
                edp_seq.append(mode_dict[f"{s}-seq"]['edp_per_go'])
            else:
                time_seq.append(0)
                edp_seq.append([0, 0, 0, 0])

            if f"{s}-rand" in mode_dict:
                time_rand.append(mode_dict[f"{s}-rand"]['time'])
                edp_rand.append(mode_dict[f"{s}-rand"]['edp_per_go'])
            else:
                time_rand.append(0)
                edp_rand.append([0, 0, 0, 0])
        return np.array(time_seq), np.array(time_rand), np.array(edp_seq), np.array(edp_rand)

    return extract_arrays(data_store['work'])

# --- 3. Fonction de tracé ---
def create_figure(time_seq, time_rand, edp_seq, edp_rand, title_prefix, filename):
    if np.sum(time_seq) == 0 and np.sum(time_rand) == 0:
        print(f"[Erreur] Aucune donnée à tracer pour {title_prefix}")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

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

    bottom_seq = np.zeros(len(x))
    bottom_rand = np.zeros(len(x))
    for i in range(4):
        ax2.bar(x - width/2, edp_seq[:, i], width, bottom=bottom_seq, color=colors[i], edgecolor='black')
        ax2.bar(x + width/2, edp_rand[:, i], width, bottom=bottom_rand, color=colors[i], edgecolor='black', hatch='//')
        bottom_seq += edp_seq[:, i]
        bottom_rand += edp_rand[:, i]

    ax2.set_xticks(x)
    ax2.set_xticklabels(scenarios)
    ax2.set_ylabel(f'EDP per GB (J·s/GB, {GB_PROCESSED} GB processed)', fontweight='bold')
    ax2.set_title(f'{title_prefix} - EDP Distribution per GB', fontsize=14)
    ax2.grid(axis='y', linestyle='--', alpha=0.7)

    for i in range(len(x)):
        ax2.text(x[i] - width/2, bottom_seq[i] + (max(bottom_rand)*0.02), f"{bottom_seq[i]:.0f}", ha='center', va='bottom', fontsize=10)
        ax2.text(x[i] + width/2, bottom_rand[i] + (max(bottom_rand)*0.02), f"{bottom_rand[i]:.0f}", ha='center', va='bottom', fontsize=10)

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

print("=== Génération EDP/Go - 4 scénarios NUMA (Work-Bound) ===")
data_work = load_global_rapl_data(global_path)

if data_work:
    wb_time_seq, wb_time_rand, wb_edp_seq, wb_edp_rand = data_work
    create_figure(wb_time_seq, wb_time_rand, wb_edp_seq, wb_edp_rand,
                  "WORK-BOUND Mode", "analysis/edp_per_go_workbound_scenarios.png")
