import pandas as pd
import matplotlib.pyplot as plt
import os

# --- 1. Load the data ---
csv_path = "results/RAPL/scalability_energy_results.csv"
if not os.path.exists(csv_path):
    print(f"Error: File {csv_path} not found.")
    exit(1)

df = pd.read_csv(csv_path)

# Convert micro-Joules to Joules
df['total_joules'] = df['total_uj'] / 1_000_000

# Ensure X-axis is in the correct categorical order
# Updated X-axis order including N6 and N10
df['cores'] = pd.Categorical(df['cores'], categories=['N4', 'N6', 'N8', 'N10', 'N12'], ordered=True)

# Define common styles for consistency across plots
scenarios = ['baseline', 'extreme', 'cross-numa', 'extreme-cross']
colors = {'baseline': '#2ca02c', 'extreme': '#d62728', 'cross-numa': '#ff7f0e', 'extreme-cross': '#9467bd'}
markers = {'baseline': 'o', 'extreme': 's', 'cross-numa': '^', 'extreme-cross': 'D'}

# --- Plotting Function ---
def create_plot(pattern_name, title_prefix):
    df_filtered = df[df['pattern'] == pattern_name].sort_values('cores')
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(f"{title_prefix} - {pattern_name.capitalize()} Access Pattern", fontsize=16, fontweight='bold')

    for sc in scenarios:
        data = df_filtered[df_filtered['scenario'] == sc]
        if not data.empty:
            # Execution Time Plot
            ax1.plot(data['cores'], data['duration_s'], marker=markers[sc], color=colors[sc], 
                     label=sc, linewidth=2.5, markersize=8)
            # Energy Plot
            ax2.plot(data['cores'], data['total_joules'], marker=markers[sc], color=colors[sc], 
                     label=sc, linewidth=2.5, markersize=8)

    # Axis 1: Time Formatting
    ax1.set_title("Execution Time", fontsize=14)
    ax1.set_ylabel("Time (Seconds)", fontsize=12)
    ax1.set_xlabel("Number of Cores", fontsize=12)
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.legend(title="NUMA Scenarios")

    # Axis 2: Energy Formatting
    ax2.set_title("Energy Consumption", fontsize=14)
    ax2.set_ylabel("Total Energy (Joules)", fontsize=12)
    ax2.set_xlabel("Number of Cores", fontsize=12)
    ax2.grid(True, linestyle='--', alpha=0.7)
    ax2.legend(title="NUMA Scenarios")

    plt.tight_layout()
    output_file = f"analysis/scalability_{pattern_name}.png"
    plt.savefig(output_file, dpi=300)
    print(f"Plot successfully generated: {output_file}")

# --- 2. Generate both plots ---
create_plot('seq', 'Energy vs Cores')
create_plot('rand', 'Energy vs Cores')