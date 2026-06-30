import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

def plot_scaling_efficiency(rapl_csv, inst_csv):
    # 1. Load Data
    # The 'names' argument applies these labels to the headerless CSV columns
    rapl_cols = ['pattern', 'n_cores', 'scen_type', 'time', 'pkg_only_total_uj', 'pkg0', 'pkg1', 'dram0', 'dram1']
    df_rapl = pd.read_csv(rapl_csv, header=0, names=rapl_cols)
    df_inst = pd.read_csv(inst_csv)
    
    # 2. Data Cleaning for perfect merging
    df_rapl['n_cores'] = df_rapl['n_cores'].str.replace('N', '').astype(int)
    df_rapl['scen_type'] = df_rapl['scen_type'].str.strip()
    df_rapl['pattern'] = df_rapl['pattern'].str.strip()
    
    # 3. CRITICAL CORRECTION OF TOTAL ENERGY
    # Recalculate true total by summing all hardware components (Processors + RAM)
    df_rapl['true_total_uj'] = df_rapl['pkg0'] + df_rapl['pkg1'] + df_rapl['dram0'] + df_rapl['dram1']
    
    # 4. MEDIAN CALCULATION
    # Group multiple runs (e.g., 3 runs of baseline-N4-rand) and take the median
    df_rapl_median = df_rapl.groupby(['pattern', 'n_cores', 'scen_type']).median(numeric_only=True).reset_index()
    
    # 5. Merge DataFrames
    df_merged = pd.merge(df_rapl_median, df_inst, on=['scen_type', 'n_cores', 'pattern'])
    
    # 6. Calculate Efficiency
    # micro-Joules (uJ) * 1000 = nano-Joules (nJ)
    df_merged['efficiency_nj_inst'] = (df_merged['true_total_uj'] * 1000) / df_merged['instructions']
    
    # --- Define Color Palette ---
    custom_palette = {
        'baseline': '#2ca02c',       # Green
        'extreme': '#d62728',        # Red
        'cross-numa': '#ff7f0e',     # Orange
        'extreme-cross': '#9467bd',  # Purple
        'native': '#1f77b4'          # Blue
    }
    
    # 7. Create TWO side-by-side plots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
    sns.set_style("whitegrid")
    
    # ---- LEFT Plot (Sequential) ----
    df_seq = df_merged[df_merged['pattern'] == 'seq']
    sns.lineplot(
        data=df_seq, x='n_cores', y='efficiency_nj_inst', 
        hue='scen_type', marker='o', palette=custom_palette, 
        ax=ax1, linewidth=2.5, markersize=8
    )
    ax1.set_title('Sequential Access - Efficiency Scalability', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Number of CPU Cores (Pods)', fontsize=12)
    ax1.set_ylabel('Energy Cost per Instruction (nJ/inst)', fontsize=12, fontweight='bold')
    ax1.grid(True, linestyle='--', alpha=0.7)
    
    # ---- RIGHT Plot (Random) ----
    df_rand = df_merged[df_merged['pattern'] == 'rand']
    sns.lineplot(
        data=df_rand, x='n_cores', y='efficiency_nj_inst', 
        hue='scen_type', marker='s', palette=custom_palette, # square markers for rand
        ax=ax2, linewidth=2.5, markersize=8
    )
    ax2.set_title('Random Access - Efficiency Scalability', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Number of CPU Cores (Pods)', fontsize=12)
    ax2.set_ylabel('') # No need to repeat the Y-axis label
    ax2.grid(True, linestyle='--', alpha=0.7)
    
    # Legend management (Keep only one clean legend on the right)
    ax1.get_legend().remove()
    handles, labels = ax2.get_legend_handles_labels()
    ax2.legend(handles=handles, labels=labels, title='NUMA Scenarios', bbox_to_anchor=(1.05, 1), loc='upper left', frameon=True)
    
    plt.tight_layout()
    
    os.makedirs("analysis", exist_ok=True)
    plt.savefig('analysis/scaling_efficiency_split.png', dpi=300, bbox_inches='tight')
    print("[SUCCESS] Plot generated: analysis/scaling_efficiency_split_complete.png")

# Execution
if __name__ == "__main__":
    plot_scaling_efficiency("results/RAPL/scalability_energy_results_complete.csv", "total_instructions_work_scalability.csv")