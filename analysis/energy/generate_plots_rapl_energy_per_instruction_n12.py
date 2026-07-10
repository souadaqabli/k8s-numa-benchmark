import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import os

# --- 1. Paramètres Globaux ---
# 4 scénarios de contention NUMA pris à N=12 + Native à N4 et N12 (rôle de "overload").
RAPL_CSV = "results/RAPL/scalability_energy_results_utiles.csv"
INST_CSV = "total_instructions_work_scalability.csv"
RAPL_COLS = ['pattern', 'n_cores', 'scen_type', 'time', 'pkg_only_total_uj', 'pkg0', 'pkg1', 'dram0', 'dram1']

CATEGORIES = ['Baseline', 'Extreme', 'Cross-NUMA', 'Ex-Cross', 'Native (N12)']
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
comp_labels = ['PKG 0', 'PKG 1', 'DRAM 0', 'DRAM 1']

SCEN_LABELS = {'baseline': 'Baseline', 'extreme': 'Extreme', 'cross-numa': 'Cross-NUMA', 'extreme-cross': 'Ex-Cross'}


def category_for(row):
    if row['scen_type'] == 'native':
        return f"Native (N{row['n_cores']})"
    return SCEN_LABELS[row['scen_type']]


def load_data(rapl_csv, inst_csv):
    # Le fichier RAPL n'a pas d'en-tête : on nomme les colonnes explicitement.
    df = pd.read_csv(rapl_csv, header=None, names=RAPL_COLS)
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

    # Fusion avec le nombre d'instructions (même clé : scen_type, n_cores, pattern)
    df_inst = pd.read_csv(inst_csv)
    df_inst['scen_type'] = df_inst['scen_type'].str.strip().str.lower()
    df_inst['pattern'] = df_inst['pattern'].str.strip().str.lower()
    df_merged = pd.merge(df_median, df_inst, on=['scen_type', 'n_cores', 'pattern'], how='left')

    if df_merged['instructions'].isna().any():
        missing = df_merged[df_merged['instructions'].isna()][['pattern', 'n_cores', 'scen_type']]
        print(f"[Warning] Instructions manquantes pour :\n{missing}")

    # nJ/instruction par composant matériel (uJ * 1000 = nJ)
    for comp in ['pkg0', 'pkg1', 'dram0', 'dram1']:
        df_merged[f'{comp}_nj_inst'] = (df_merged[comp] * 1000) / df_merged['instructions']

    df_merged['category'] = df_merged.apply(category_for, axis=1)
    return df_merged


def extract_arrays(df_merged, pattern):
    sub = df_merged[df_merged['pattern'] == pattern].set_index('category')
    time_arr, metric_arr = [], []
    for cat in CATEGORIES:
        if cat in sub.index and pd.notna(sub.loc[cat, 'instructions']):
            row = sub.loc[cat]
            time_arr.append(row['time'])
            metric_arr.append([row['pkg0_nj_inst'], row['pkg1_nj_inst'], row['dram0_nj_inst'], row['dram1_nj_inst']])
        else:
            time_arr.append(0 if cat not in sub.index else sub.loc[cat, 'time'])
            metric_arr.append([0, 0, 0, 0])
    return np.array(time_arr), np.array(metric_arr)


def create_figure(time_seq, time_rand, metric_seq, metric_rand, filename):
    if np.sum(time_seq) == 0 and np.sum(time_rand) == 0:
        print("[Erreur] Aucune donnée à tracer.")
        return

    fig, axs = plt.subplots(2, 2, figsize=(16, 12))
    ax_seq_time, ax_seq_eff = axs[0, 0], axs[0, 1]
    ax_rand_time, ax_rand_eff = axs[1, 0], axs[1, 1]

    width_bar = 0.6
    x_indices = np.arange(len(CATEGORIES))

    # ---- ROW 1 : SEQUENTIAL ----
    ax_seq_time.bar(x_indices, time_seq, width_bar, color='lightblue', edgecolor='black')
    ax_seq_time.set_xticks(x_indices)
    ax_seq_time.set_xticklabels(CATEGORIES, rotation=15)
    ax_seq_time.set_ylabel('Execution Time (seconds)', fontweight='bold')
    ax_seq_time.set_title('N=12 - SEQUENTIAL TIME', fontsize=12, fontweight='bold')
    ax_seq_time.grid(axis='y', linestyle='--', alpha=0.7)
    for i in range(len(x_indices)):
        if time_seq[i] > 0:
            ax_seq_time.text(x_indices[i], time_seq[i] + (np.max(time_seq)*0.02), f"{int(time_seq[i])}s", ha='center', va='bottom', fontsize=10)

    bottom_seq = np.zeros(len(x_indices))
    for i in range(4):
        ax_seq_eff.bar(x_indices, metric_seq[:, i], width_bar, bottom=bottom_seq, color=colors[i], edgecolor='black')
        bottom_seq += metric_seq[:, i]
    ax_seq_eff.set_xticks(x_indices)
    ax_seq_eff.set_xticklabels(CATEGORIES, rotation=15)
    ax_seq_eff.set_ylabel('Cost per Instruction (nJ/inst)', fontweight='bold')
    ax_seq_eff.set_title('N=12 - SEQUENTIAL EFFICIENCY', fontsize=12, fontweight='bold')
    ax_seq_eff.grid(axis='y', linestyle='--', alpha=0.7)
    max_y_seq = np.max(bottom_seq) if np.max(bottom_seq) > 0 else 1
    for i in range(len(x_indices)):
        if bottom_seq[i] > 0:
            ax_seq_eff.text(x_indices[i], bottom_seq[i] + (max_y_seq*0.02), f"{bottom_seq[i]:.1f}", ha='center', va='bottom', fontsize=9, fontweight='bold')

    # ---- ROW 2 : RANDOM ----
    ax_rand_time.bar(x_indices, time_rand, width_bar, color='salmon', edgecolor='black', hatch='//')
    ax_rand_time.set_xticks(x_indices)
    ax_rand_time.set_xticklabels(CATEGORIES, rotation=15)
    ax_rand_time.set_ylabel('Execution Time (seconds)', fontweight='bold')
    ax_rand_time.set_title('N=12 - RANDOM TIME', fontsize=12, fontweight='bold')
    ax_rand_time.grid(axis='y', linestyle='--', alpha=0.7)
    for i in range(len(x_indices)):
        if time_rand[i] > 0:
            ax_rand_time.text(x_indices[i], time_rand[i] + (np.max(time_rand)*0.02), f"{int(time_rand[i])}s", ha='center', va='bottom', fontsize=10)

    bottom_rand = np.zeros(len(x_indices))
    for i in range(4):
        ax_rand_eff.bar(x_indices, metric_rand[:, i], width_bar, bottom=bottom_rand, color=colors[i], edgecolor='black', hatch='//')
        bottom_rand += metric_rand[:, i]
    ax_rand_eff.set_xticks(x_indices)
    ax_rand_eff.set_xticklabels(CATEGORIES, rotation=15)
    ax_rand_eff.set_ylabel('Cost per Instruction (nJ/inst)', fontweight='bold')
    ax_rand_eff.set_title('N=12 - RANDOM EFFICIENCY', fontsize=12, fontweight='bold')
    ax_rand_eff.grid(axis='y', linestyle='--', alpha=0.7)
    max_y_rand = np.max(bottom_rand) if np.max(bottom_rand) > 0 else 1
    for i in range(len(x_indices)):
        if bottom_rand[i] > 0:
            ax_rand_eff.text(x_indices[i], bottom_rand[i] + (max_y_rand*0.02), f"{bottom_rand[i]:.1f}", ha='center', va='bottom', fontsize=9, fontweight='bold')

    legend_elements = [mpatches.Patch(facecolor=colors[i], edgecolor='black', label=comp_labels[i]) for i in range(4)]
    legend_elements.append(mpatches.Patch(facecolor='lightblue', edgecolor='black', label='Time (Seq)'))
    legend_elements.append(mpatches.Patch(facecolor='salmon', edgecolor='black', hatch='//', label='Time (Rand)'))
    fig.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, 0.98), ncol=6, fontsize=11)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    os.makedirs("analysis", exist_ok=True)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"[OK] Plot successfully generated: {filename}")
    plt.close()


if __name__ == "__main__":
    print("=== Génération Énergie par Instruction - 4 scénarios N12 + Native N12 ===")
    df_merged = load_data(RAPL_CSV, INST_CSV)

    time_seq, metric_seq = extract_arrays(df_merged, 'seq')
    time_rand, metric_rand = extract_arrays(df_merged, 'rand')

    create_figure(time_seq, time_rand, metric_seq, metric_rand,
                  "analysis/energy_per_instruction_n12_native.png")
