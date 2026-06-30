import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from parser_rapl_v2 import get_energy_medians_v2
from parser_perf_v2 import extract_massive_micro_metrics

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "analysis_v2")

RAPL_PATH = "results/RAPL/scalability_energy_results_complete.csv"  # The path to Approach 2 RAPL CSV
PERF_DIR = "../sdn2_remote_data"         # The main folder containing all the runs

def generate_side_by_side_plots(df):
    """
    Generates Split-View plots: N=4 on the left, N=12 on the right.
    Shares the Y-axis so the energy jump is visually obvious.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
    
    # Strictly filter to N=4 and N=12
    df_filtered = df[df['cores_int'].isin([4, 12])].copy()
    
    print(f"\n--- [DEBUG] Generating Split-View Plots for {len(df_filtered)} points. ---")
    
    pattern_palette = {'seq': '#1f77b4', 'rand': '#d62728'}

    # ==========================================
    # PLOT 1: IPC vs Energy Cost (Side-by-Side)
    # ==========================================
    # sharey=True is the magic trick: it forces both sides to use the same Y scale
    fig1, axes1 = plt.subplots(1, 2, figsize=(16, 7), sharey=True)
    fig1.suptitle('Scalability Impact: IPC vs Energy Cost', fontweight='bold', fontsize=16)
    
    for i, cores in enumerate([4, 12]):
        ax = axes1[i]
        df_sub = df_filtered[df_filtered['cores_int'] == cores]
        
        sns.scatterplot(data=df_sub, x='ipc', y='nj_per_inst', 
                        hue='pattern', palette=pattern_palette, 
                        s=150, edgecolor='black', alpha=0.9, ax=ax, legend=(i==1))
        
        # Annotate just the scenario name (baseline, extreme, etc.)
        for _, row in df_sub.iterrows():
            ax.annotate(row['scenario'], 
                        (row['ipc'], row['nj_per_inst']),
                        xytext=(8, 0), textcoords='offset points', 
                        fontsize=10, fontweight='bold', color='#333333', va='center')
        
        # Local Trendline
        if len(df_sub) > 1:
            z = np.polyfit(df_sub['ipc'], df_sub['nj_per_inst'], 1)
            ax.plot(df_sub['ipc'], np.poly1d(z)(df_sub['ipc']), color="gray", linestyle="--", alpha=0.5)
            
        ax.set_title(f'Load: {cores} Pods', fontweight='bold', color='#444444')
        ax.set_xlabel('Execution Efficiency (Global IPC)', fontweight='bold')
        
        # Only set Y label on the far left plot
        if i == 0:
            ax.set_ylabel('Hardware Cost (nJ / instruction)', fontweight='bold')
        else:
            ax.set_ylabel('')
            
        if i == 1:
            ax.legend(title="Pattern", bbox_to_anchor=(1.02, 1), loc='upper left')

    plt.tight_layout()
    fig1.savefig(os.path.join(OUTPUT_DIR, 'v2_split_ipc.png'), dpi=300, bbox_inches='tight')
    plt.close(fig1)

    # ==========================================
    # PLOT 2: MPKI vs Energy Cost (Side-by-Side)
    # ==========================================
    fig2, axes2 = plt.subplots(1, 2, figsize=(16, 7), sharey=True)
    fig2.suptitle('Scalability Impact: Memory Stalls (MPKI) vs Energy Cost', fontweight='bold', fontsize=16)
    
    for i, cores in enumerate([4, 12]):
        ax = axes2[i]
        df_sub = df_filtered[df_filtered['cores_int'] == cores]
        
        sns.scatterplot(data=df_sub, x='llc_mpki', y='nj_per_inst', 
                        hue='pattern', palette=pattern_palette, 
                        s=150, edgecolor='black', alpha=0.9, ax=ax, legend=(i==1))
        
        for _, row in df_sub.iterrows():
            ax.annotate(row['scenario'], 
                        (row['llc_mpki'], row['nj_per_inst']),
                        xytext=(8, 0), textcoords='offset points', 
                        fontsize=10, fontweight='bold', color='#333333', va='center')
        
        if len(df_sub) > 1:
            z2 = np.polyfit(df_sub['llc_mpki'], df_sub['nj_per_inst'], 1)
            ax.plot(df_sub['llc_mpki'], np.poly1d(z2)(df_sub['llc_mpki']), color="gray", linestyle="--", alpha=0.5)
            
        ax.set_title(f'Load: {cores} Pods', fontweight='bold', color='#444444')
        ax.set_xlabel('Memory Bottleneck (L3 MPKI)', fontweight='bold')
        
        if i == 0:
            ax.set_ylabel('Hardware Cost (nJ / instruction)', fontweight='bold')
        else:
            ax.set_ylabel('')
            
        if i == 1:
            ax.legend(title="Pattern", bbox_to_anchor=(1.02, 1), loc='upper left')

    plt.tight_layout()
    fig2.savefig(os.path.join(OUTPUT_DIR, 'v2_split_mpki.png'), dpi=300, bbox_inches='tight')
    plt.close(fig2)


def main():
    print("=== V2 Split-View Pipeline Started ===")
    
    rapl_data = get_energy_medians_v2(RAPL_PATH)
    perf_data = extract_massive_micro_metrics(PERF_DIR)
    
    if not rapl_data or not perf_data:
        sys.exit(1)
        
    final_merged_results = []
    
    for key, metrics in perf_data.items():
        if key in rapl_data:
            median_joules = rapl_data[key]
            total_inst = metrics["total_instructions"]
            
            if total_inst > 0:
                nj_per_inst = (median_joules / total_inst) * 1_000_000_000
                parts = key.split('-')
                pattern = parts[-1]        
                cores_str = parts[-2]      
                cores_int = int(cores_str.replace('n', ''))
                scenario = "-".join(parts[:-2])
                
                final_merged_results.append({
                    'unified_key': key, 'scenario': scenario, 'cores_str': cores_str,
                    'cores_int': cores_int, 'pattern': pattern, 'ipc': metrics['ipc'],
                    'llc_mpki': metrics['llc_mpki'], 'nj_per_inst': round(nj_per_inst, 2)
                })
                
    if final_merged_results:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        df_final = pd.DataFrame(final_merged_results)
        
        print(f"\n[INFO] Data extracted. Generating Split-View charts...")
        df_final.to_csv(os.path.join(OUTPUT_DIR, "v2_scientific_summary.csv"), index=False)
        generate_side_by_side_plots(df_final)
        print("\n[SUCCESS] Split graphs generated! Check the 'analysis_v2' folder.")

if __name__ == "__main__":
    main()