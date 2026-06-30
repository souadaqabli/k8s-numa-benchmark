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

# =====================================================================
# ### NEW: TIME-BASED NORMALIZATION (Average Power in Watts)
# =====================================================================

# Calculate Average Power (Watts = Joules / Seconds)
# This perfectly normalizes energy consumption against execution time
df['avg_power_w'] = df['total_joules'] / df['duration_s']

# =====================================================================

# Define common styles for consistency across plots
scenarios = ['baseline', 'extreme', 'cross-numa', 'extreme-cross','native']
colors = {'baseline': '#2ca02c', 'extreme': '#d62728', 'cross-numa': '#ff7f0e', 'extreme-cross': '#9467bd','native': '#1f77b4'}
markers = {'baseline': 'o', 'extreme': 's', 'cross-numa': '^', 'extreme-cross': 'D','native': '*'}

# --- Plotting Function ---
def create_plot(pattern_name, title_prefix):
    df_filtered = df[df['pattern'] == pattern_name]
    
    if df_filtered.empty:
        print(f"No data found for pattern {pattern_name}. Skipping plot.")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(f"NORMALIZED {title_prefix} - {pattern_name.capitalize()} Access Pattern", fontsize=16, fontweight='bold')

    for sc in scenarios:
        data = df_filtered[df_filtered['scenario'] == sc]
        if not data.empty:
            
            # --- STATISTICAL CALCULATION ON NEW METRICS ---
            stats = data.groupby('cores', observed=False).agg(
                # Median, min, max for Performance (Execution Time)
                time_med=('duration_s', 'median'),
                time_min=('duration_s', 'min'),
                time_max=('duration_s', 'max'),
                
                # Median, min, max for Normalized Energy (Average Power)
                power_med=('avg_power_w', 'median'),
                power_min=('avg_power_w', 'min'),
                power_max=('avg_power_w', 'max')
            ).reset_index()

            # Drop empty rows (if a core count hasn't been tested yet)
            stats = stats.dropna()

            # --- PLOT 1: PERFORMANCE (Execution Time) ---
            # Median line
            ax1.plot(stats['cores'], stats['time_med'], marker=markers[sc], color=colors[sc], 
                     label=sc, linewidth=2.5, markersize=8)
            # Shaded area (Min -> Max)
            ax1.fill_between(stats['cores'], stats['time_min'], stats['time_max'], 
                             color=colors[sc], alpha=0.15)

            # --- PLOT 2: NORMALIZED ENERGY (Average Power in Watts) ---
            # Median line
            ax2.plot(stats['cores'], stats['power_med'], marker=markers[sc], color=colors[sc], 
                     label=sc, linewidth=2.5, markersize=8)
            # Shaded area (Min -> Max)
            ax2.fill_between(stats['cores'], stats['power_min'], stats['power_max'], 
                             color=colors[sc], alpha=0.15)

    # Axis 1: Performance Formatting
    ax1.set_title("System Performance (Execution Time)", fontsize=14)
    ax1.set_ylabel("Time (Seconds) - Lower is better", fontsize=12)
    ax1.set_xlabel("Number of Cores", fontsize=12)
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.legend(title="NUMA Scenarios")

    # Axis 2: Power Formatting
    ax2.set_title("Normalized Energy (Average Power)", fontsize=14)
    ax2.set_ylabel("Average Power (Watts)", fontsize=12)
    ax2.set_xlabel("Number of Cores", fontsize=12)
    ax2.grid(True, linestyle='--', alpha=0.7)
    ax2.legend(title="NUMA Scenarios")

    plt.tight_layout()
    
    # Create the output directory if it doesn't exist
    os.makedirs("analysis", exist_ok=True)
    
    # Save the normalized plot with a new name
    output_file = f"analysis/scalability_{pattern_name}_power_normalized_complete.png"
    plt.savefig(output_file, dpi=300)
    print(f"Plot successfully generated: {output_file}")

# --- 2. Generate both plots ---
create_plot('seq', 'Power vs Cores')
create_plot('rand', 'Power vs Cores')