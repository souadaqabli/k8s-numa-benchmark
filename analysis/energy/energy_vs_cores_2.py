import pandas as pd
import matplotlib.pyplot as plt
import os

# --- 1. Load the data ---
csv_path = "results/RAPL/scalability_energy_results_complete.csv"
if not os.path.exists(csv_path):
    print(f"Error: File {csv_path} not found.")
    exit(1)

df = pd.read_csv(csv_path)

# Convert micro-Joules to Joules
df['total_joules'] = df['total_uj'] / 1_000_000

# Ensure X-axis is in the correct categorical order
df['cores'] = pd.Categorical(df['cores'], categories=['N4', 'N6', 'N8', 'N10', 'N12'], ordered=True)

# Define common styles for consistency across plots
scenarios = ['baseline', 'extreme', 'cross-numa', 'extreme-cross']
colors = {'baseline': '#2ca02c', 'extreme': '#d62728', 'cross-numa': '#ff7f0e', 'extreme-cross': '#9467bd'}
markers = {'baseline': 'o', 'extreme': 's', 'cross-numa': '^', 'extreme-cross': 'D'}

# --- Plotting Function ---
def create_plot(pattern_name, title_prefix):
    df_filtered = df[df['pattern'] == pattern_name]
    
    # On vérifie s'il y a des données pour ce pattern avant de créer l'image
    if df_filtered.empty:
        print(f"Aucune donnée pour le pattern {pattern_name}. Graphique ignoré.")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(f"{title_prefix} - {pattern_name.capitalize()} Access Pattern", fontsize=16, fontweight='bold')

    for sc in scenarios:
        data = df_filtered[df_filtered['scenario'] == sc]
        if not data.empty:
            
            # --- CALCUL STATISTIQUE (Médiane, Min, Max) ---
            # On groupe par paliers (N4, N6...) et on calcule les stats pour chaque point
            stats = data.groupby('cores', observed=False).agg(
                dur_med=('duration_s', 'median'),
                dur_min=('duration_s', 'min'),
                dur_max=('duration_s', 'max'),
                joules_med=('total_joules', 'median'),
                joules_min=('total_joules', 'min'),
                joules_max=('total_joules', 'max')
            ).reset_index()

            # On supprime les lignes vides (si un palier n'a pas encore été testé)
            stats = stats.dropna()

            # --- PLOT 1 : TEMPS D'EXÉCUTION ---
            # Ligne de la médiane
            ax1.plot(stats['cores'], stats['dur_med'], marker=markers[sc], color=colors[sc], 
                     label=sc, linewidth=2.5, markersize=8)
            # Zone ombrée (Min -> Max)
            ax1.fill_between(stats['cores'], stats['dur_min'], stats['dur_max'], 
                             color=colors[sc], alpha=0.15)

            # --- PLOT 2 : CONSOMMATION D'ÉNERGIE ---
            # Ligne de la médiane
            ax2.plot(stats['cores'], stats['joules_med'], marker=markers[sc], color=colors[sc], 
                     label=sc, linewidth=2.5, markersize=8)
            # Zone ombrée (Min -> Max)
            ax2.fill_between(stats['cores'], stats['joules_min'], stats['joules_max'], 
                             color=colors[sc], alpha=0.15)

    # Axis 1: Time Formatting
    ax1.set_title("Execution Time (Median & Min/Max Range)", fontsize=14)
    ax1.set_ylabel("Time (Seconds)", fontsize=12)
    ax1.set_xlabel("Number of Cores", fontsize=12)
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.legend(title="NUMA Scenarios")

    # Axis 2: Energy Formatting
    ax2.set_title("Energy Consumption (Median & Min/Max Range)", fontsize=14)
    ax2.set_ylabel("Total Energy (Joules)", fontsize=12)
    ax2.set_xlabel("Number of Cores", fontsize=12)
    ax2.grid(True, linestyle='--', alpha=0.7)
    ax2.legend(title="NUMA Scenarios")

    plt.tight_layout()
    # Création du dossier d'analyse s'il n'existe pas
    os.makedirs("analysis", exist_ok=True)
    output_file = f"analysis/scalability_{pattern_name}_2.png"
    plt.savefig(output_file, dpi=300)
    print(f"Plot successfully generated: {output_file}")

# --- 2. Generate both plots ---
create_plot('seq', 'Energy vs Cores')
create_plot('rand', 'Energy vs Cores')