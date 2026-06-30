import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Chargement des données
csv_path = "/home/sdnuser/k8s-numa-benchmark/results/RAPL/rapl_global_results_3.csv"
if not os.path.exists(csv_path):
    csv_path = "rapl_global_results_3.csv"

df = pd.read_csv(csv_path)
df['total_j'] = df['total_uj'] / 1_000_000

def get_architecture(scenario):
    if scenario.startswith('baseline'): return 'Baseline'
    elif scenario.startswith('cross-numa'): return 'Cross-NUMA'
    elif scenario.startswith('extreme-cross'): return 'Extreme Cross'
    elif scenario.startswith('extreme'): return 'Extreme Local'
    return 'Unknown'

df['Architecture'] = df['scenario'].apply(get_architecture)
df['Size'] = df['target_size_kb'].map({262144: "256 MB", 524288: "512 MB", 1048576: "1 GB"})

arch_order = ['Baseline', 'Cross-NUMA', 'Extreme Local', 'Extreme Cross']
size_order = ['256 MB', '512 MB', '1 GB']
df['Size'] = pd.Categorical(df['Size'], categories=size_order, ordered=True)

# ---> FILTRAGE EXCLUSIF SUR LE MODE TIME-BOUND <---
df_time = df[df['scenario'].str.contains('-time-') | df['scenario'].str.endswith('-time')]

sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 11})

# Création du dossier cible spécifique
output_dir = "/home/sdnuser/k8s-numa-benchmark/results/RAPL/plots/time_bound"
os.makedirs(output_dir, exist_ok=True)

# PALETTE DE COULEURS FIXE
size_palette = {
    "256 MB": "#4C72B0",  # Bleu
    "512 MB": "#DD8452",  # Orange
    "1 GB": "#C44E52"     # Rouge
}

def generate_grouped_plot_timebound_uniform(pattern_keyword, title_prefix, filename):
    subset = df_time[df_time['scenario'].str.contains(pattern_keyword)]
    if subset.empty: return
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.5))
    fig.suptitle(f"Performance and Energy - {title_prefix} Access (Time-Bound : 120s Stress)", fontsize=16, fontweight='bold', y=0.95)

    # --- LEFT PLOT: TIME ---
    sns.barplot(data=subset, x='Architecture', y='duration_s', hue='Size', order=arch_order, hue_order=size_order, ax=axes[0], palette=size_palette)
    # TITRES IDENTIQUES AU WORK-BOUND
    axes[0].set_title("Execution Time by Architecture", fontsize=14)
    axes[0].set_ylabel("Time (Seconds)")
    axes[0].set_xlabel("K8s NUMA Placement")
    
    for p in axes[0].patches:
        height = p.get_height()
        if pd.notna(height) and height > 0:
            axes[0].annotate(f"{int(height)}s", (p.get_x() + p.get_width() / 2., height), ha='center', va='bottom', fontsize=10, xytext=(0, 3), textcoords='offset points')

    # --- RIGHT PLOT: ENERGY ---
    sns.barplot(data=subset, x='Architecture', y='total_j', hue='Size', order=arch_order, hue_order=size_order, ax=axes[1], palette=size_palette)
    # TITRES IDENTIQUES AU WORK-BOUND
    axes[1].set_title("Energy Consumption by Architecture", fontsize=14)
    axes[1].set_ylabel("Total Energy (Joules)")
    axes[1].set_xlabel("K8s NUMA Placement")
    
    for p in axes[1].patches:
        height = p.get_height()
        if pd.notna(height) and height > 0:
            axes[1].annotate(f"{int(height)}J", (p.get_x() + p.get_width() / 2., height), ha='center', va='bottom', fontsize=10, xytext=(0, 3), textcoords='offset points')

    plt.tight_layout()
    plt.subplots_adjust(top=0.85)
    
    save_path = f"{output_dir}/{filename}.png"
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"[OK] Graphique généré : {save_path}")

print("Génération des graphiques groupés Time-Bound unifiés...")
generate_grouped_plot_timebound_uniform("-seq-", "Sequential", "summary_sequential_timebound")
generate_grouped_plot_timebound_uniform("-rand-", "Random", "summary_random_timebound")
print("Terminé !")