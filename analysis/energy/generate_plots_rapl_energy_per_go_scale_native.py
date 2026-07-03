import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# --- Volume de données traité par pod (mode WORK-BOUND) ---
# script_controlled.py boucle sur 6 tailles de buffer x 2 modes (read+write),
# et mem_stress_controlled.py traite ~10 GiB par sous-test (--target-mb 10240).
# => 6 * 2 * 10 = 120 GiB traités PAR POD.
GB_PER_POD = 6 * 2 * 10

def plot_scaling_energy_per_go(rapl_csv):
    # 1. Load Data
    rapl_cols = ['pattern', 'n_cores', 'scen_type', 'time', 'pkg_only_total_uj', 'pkg0', 'pkg1', 'dram0', 'dram1']
    df_rapl = pd.read_csv(rapl_csv, header=0, names=rapl_cols)

    # 2. Data Cleaning
    df_rapl['n_cores'] = df_rapl['n_cores'].str.replace('N', '').astype(int)
    df_rapl['scen_type'] = df_rapl['scen_type'].str.strip()
    df_rapl['pattern'] = df_rapl['pattern'].str.strip()

    # N20 ignoré pour le moment
    df_rapl = df_rapl[df_rapl['n_cores'] != 20]

    # 3. CORRECTION DE L'ÉNERGIE TOTALE
    # pkg_only_total_uj (colonne 4 du CSV brut) = pkg0 + pkg1 SEULEMENT (bug), on l'ignore.
    # Le vrai total = pkg0 + pkg1 + dram0 + dram1
    df_rapl['true_total_uj'] = df_rapl['pkg0'] + df_rapl['pkg1'] + df_rapl['dram0'] + df_rapl['dram1']

    # 4. MEDIAN CALCULATION (plusieurs runs par config)
    df_rapl_median = df_rapl.groupby(['pattern', 'n_cores', 'scen_type']).median(numeric_only=True).reset_index()

    # 5. Volume de données système : n_cores pods, chacun traitant GB_PER_POD Go
    # (confirmé : deployments/scalability/{seq,rand}/N*/*.yaml ont toujours
    #  une somme de "parallelism" égale à N)
    df_rapl_median['gb_processed'] = df_rapl_median['n_cores'] * GB_PER_POD

    # 6. Calcul de l'efficacité énergétique par Go
    df_rapl_median['energy_j_per_gb'] = (df_rapl_median['true_total_uj'] / 1_000_000) / df_rapl_median['gb_processed']

    # --- Define Color Palette ---
    custom_palette = {
        'baseline': '#2ca02c',       # Green
        'extreme': '#d62728',        # Red
        'cross-numa': '#ff7f0e',     # Orange
        'extreme-cross': '#9467bd',  # Purple
        'native': '#1f77b4'          # Blue
    }

    # 7. Create TWO side-by-side plots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    sns.set_style("whitegrid")

    # ---- LEFT Plot (Sequential) ----
    df_seq = df_rapl_median[df_rapl_median['pattern'] == 'seq']
    sns.lineplot(
        data=df_seq, x='n_cores', y='energy_j_per_gb',
        hue='scen_type', marker='o', palette=custom_palette,
        ax=ax1, linewidth=2.5, markersize=8
    )
    ax1.set_title('Sequential Access - Energy per GB Scalability', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Number of CPU Cores (Pods)', fontsize=12)
    ax1.set_ylabel('Energy Cost per GB (Joules/GB)', fontsize=12, fontweight='bold')
    ax1.grid(True, linestyle='--', alpha=0.7)

    # ---- RIGHT Plot (Random) ----
    df_rand = df_rapl_median[df_rapl_median['pattern'] == 'rand']
    sns.lineplot(
        data=df_rand, x='n_cores', y='energy_j_per_gb',
        hue='scen_type', marker='s', palette=custom_palette,  # square markers for rand
        ax=ax2, linewidth=2.5, markersize=8
    )
    ax2.set_title('Random Access - Energy per GB Scalability', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Number of CPU Cores (Pods)', fontsize=12)
    ax2.set_ylabel('Energy Cost per GB (Joules/GB)', fontsize=12, fontweight='bold')
    ax2.grid(True, linestyle='--', alpha=0.7)

    # Legend management (Keep only one clean legend on the right)
    ax1.get_legend().remove()
    handles, labels = ax2.get_legend_handles_labels()
    ax2.legend(handles=handles, labels=labels, title='NUMA Scenarios', bbox_to_anchor=(1.05, 1), loc='upper left', frameon=True)

    plt.tight_layout()

    os.makedirs("analysis", exist_ok=True)
    plt.savefig('analysis/scaling_energy_per_go_native.png', dpi=300, bbox_inches='tight')
    print("[SUCCESS] Plot generated: analysis/scaling_energy_per_go_native.png")

# Execution
if __name__ == "__main__":
    plot_scaling_energy_per_go("results/RAPL/scalability_energy_results_complete.csv")
