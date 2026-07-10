import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import os

# --- 1. Paramètres Globaux ---
# 4 scénarios de contention NUMA pris à N=12 + Native à N4 et N12 (rôle de "overload").
RAPL_CSV = "results/RAPL/scalability_energy_results_utiles.csv"
RAPL_COLS = ['pattern', 'n_cores', 'scen_type', 'time', 'pkg_only_total_uj', 'pkg0', 'pkg1', 'dram0', 'dram1']

CATEGORIES = ['Baseline', 'Extreme', 'Cross-NUMA', 'Ex-Cross', 'Native (N12)']
x = np.arange(len(CATEGORIES))
width = 0.35
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
comp_labels = ['PKG 0', 'PKG 1', 'DRAM 0', 'DRAM 1']

SCEN_LABELS = {'baseline': 'Baseline', 'extreme': 'Extreme', 'cross-numa': 'Cross-NUMA', 'extreme-cross': 'Ex-Cross'}


def category_for(row):
    if row['scen_type'] == 'native':
        return f"Native (N{row['n_cores']})"
    return SCEN_LABELS[row['scen_type']]


def load_data(csv_path):
    # Le fichier n'a pas d'en-tête : on nomme les colonnes explicitement.
    df = pd.read_csv(csv_path, header=None, names=RAPL_COLS)
    df['n_cores'] = df['n_cores'].str.replace('N', '').astype(int)
    df['scen_type'] = df['scen_type'].str.strip().str.lower()
    df['pattern'] = df['pattern'].str.strip().str.lower()

    # CORRECTION DE L'ÉNERGIE TOTALE :
    # pkg_only_total_uj (colonne 5 du CSV brut) = pkg0 + pkg1 SEULEMENT (bug), on l'ignore.
    # Le vrai total = pkg0 + pkg1 + dram0 + dram1
    df['true_total_uj'] = df['pkg0'] + df['pkg1'] + df['dram0'] + df['dram1']

    # 4 scénarios NUMA à N12 + Native à N12
    scen_n12 = df[(df['n_cores'] == 12) & (df['scen_type'].isin(SCEN_LABELS.keys()))]
    native_n12 = df[(df['n_cores'] == 12) & (df['scen_type'] == 'native')]
    df_sel = pd.concat([scen_n12, native_n12], ignore_index=True)

    # Médiane sur les runs dupliqués
    df_median = df_sel.groupby(['pattern', 'n_cores', 'scen_type']).median(numeric_only=True).reset_index()
    df_median['category'] = df_median.apply(category_for, axis=1)
    return df_median


def extract_arrays(df_median, pattern):
    sub = df_median[df_median['pattern'] == pattern].set_index('category')
    time_arr, power_arr = [], []
    for cat in CATEGORIES:
        if cat in sub.index:
            row = sub.loc[cat]
            time_arr.append(row['time'])
            if row['time'] > 0:
                power_arr.append([(row['pkg0'] / 1_000_000) / row['time'], (row['pkg1'] / 1_000_000) / row['time'],
                                   (row['dram0'] / 1_000_000) / row['time'], (row['dram1'] / 1_000_000) / row['time']])
            else:
                power_arr.append([0, 0, 0, 0])
        else:
            time_arr.append(0)
            power_arr.append([0, 0, 0, 0])
    return np.array(time_arr), np.array(power_arr)


def create_figure(time_seq, time_rand, power_seq, power_rand, filename):
    if np.sum(time_seq) == 0 and np.sum(time_rand) == 0:
        print("[Erreur] Aucune donnée à tracer.")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # --- GRAPHE 1 : TEMPS ---
    ax1.bar(x - width/2, time_seq, width, label='Sequential', color='lightblue', edgecolor='black')
    ax1.bar(x + width/2, time_rand, width, label='Random', color='salmon', edgecolor='black', hatch='//')
    ax1.set_xticks(x)
    ax1.set_xticklabels(CATEGORIES, rotation=15)
    ax1.set_ylabel('Time (seconds)', fontweight='bold')
    ax1.set_title('N=12 - Execution Time', fontsize=14)
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
    ax2.set_xticklabels(CATEGORIES, rotation=15)
    ax2.set_ylabel('Average Power (Watts)', fontweight='bold')
    ax2.set_title('N=12 - Power Distribution (PKG + DRAM)', fontsize=14)
    ax2.grid(axis='y', linestyle='--', alpha=0.7)

    for i in range(len(x)):
        if bottom_seq[i] > 0:
            ax2.text(x[i] - width/2, bottom_seq[i] + (max(bottom_rand)*0.02), f"{bottom_seq[i]:.0f}", ha='center', va='bottom', fontsize=10)
        if bottom_rand[i] > 0:
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


if __name__ == "__main__":
    print("=== Génération Puissance (PKG+DRAM) - 4 scénarios N12 + Native N12 ===")
    df_median = load_data(RAPL_CSV)

    time_seq, power_seq = extract_arrays(df_median, 'seq')
    time_rand, power_rand = extract_arrays(df_median, 'rand')

    create_figure(time_seq, time_rand, power_seq, power_rand,
                  "analysis/power_n12_native.png")
