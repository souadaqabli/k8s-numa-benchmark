import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import csv

# Importing your custom modules (we keep them for structural compatibility)
from parser_rapl import get_energy_medians
from parser_perf import extraire_metriques_microarchitecturales

# --- PATH CONFIGURATION ---
RAPL_PATH = "results/RAPL/rapl_global_results_utiles.csv" 
INSTRUCTIONS_FILE = "total_instructions_work.csv"

# Updated to target both your bare-metal directory and your actual sdn4 native remote data path
PERF_PATHS = [
    "./results/RESULTS_WORK",               # Pinned / Vanilla scenarios
    "/home/sdnuser/sdn2_remote_data"        # Actual native folder path containing native-n4 and native-n16
]

def charger_dictionnaire_instructions(csv_path):
    """Loads the existing instructions CSV file."""
    if not os.path.exists(csv_path):
        return {}
    df = pd.read_csv(csv_path)
    # Clean the scenario column to ensure perfect matching
    df['scenario'] = df['scenario'].astype(str).str.strip().str.lower()
    return {row['scenario']: float(row['total_instructions']) for _, row in df.iterrows()}


def load_energy_medians_robust(csv_path):
    """
    Robust hybrid parser for RAPL energy CSV.
    Correctly handles both 8-column Bare-metal rows and 9-column Native rows.
    Calculates median energy (PKG + DRAM) and groups them by their folder name equivalents.
    """
    energy_data = {}
    if not os.path.exists(csv_path):
        print(f"[ERROR] RAPL file not found: {csv_path}")
        return {}

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].strip().lower() in ['scenario', 'pattern']:
                continue
            
            ligne_complete = " ".join(row).lower()
            
            # --- NATIVE ROW HANDLING (9 columns) ---
            if 'native' in ligne_complete:
                try:
                    pattern = row[0].strip().lower()   # seq or rand
                    cores = row[1].strip().lower()     # n4, n16, etc.
                    key = f"native-{cores}-{pattern}"  # e.g. native-n4-seq
                    
                    pkg0_j = float(row[5]) / 1_000_000
                    pkg1_j = float(row[6]) / 1_000_000
                    dram0_j = float(row[7]) / 1_000_000
                    dram1_j = float(row[8]) / 1_000_000
                    
                    total_j = pkg0_j + pkg1_j + dram0_j + dram1_j
                    if key not in energy_data:
                        energy_data[key] = []
                    energy_data[key].append(total_j)
                except (ValueError, IndexError):
                    continue
            
            # --- BARE-METAL ROW HANDLING (8 columns) ---
            elif len(row) >= 8:
                try:
                    key = row[0].strip().lower()       # e.g. baseline-seq-work
                    if 'work' not in key:
                        continue                       # Only analyze work-bound phases
                    
                    pkg0_j = float(row[4]) / 1_000_000
                    pkg1_j = float(row[5]) / 1_000_000
                    dram0_j = float(row[6]) / 1_000_000
                    dram1_j = float(row[7]) / 1_000_000
                    
                    total_j = pkg0_j + pkg1_j + dram0_j + dram1_j
                    if key not in energy_data:
                        energy_data[key] = []
                    energy_data[key].append(total_j)
                except (ValueError, IndexError):
                    continue

    # Compute median to eliminate OS Jitter
    rapl_dict = {}
    for key, values in energy_data.items():
        rapl_dict[key] = float(np.median(values))
        
    print(f"[parser_rapl_robust] {len(rapl_dict)} unique scenarios smoothed via median.")
    return rapl_dict


def map_folder_to_instruction_key(folder_name):
    """
    Translates a folder name into its matching key inside total_instructions_work.csv
    Examples:
      'native-n4-seq'    -> 'native-seq'
      'native-n16-rand'  -> 'native-overload-rand'
      'baseline-seq-work' -> 'baseline-seq-work'
    """
    if folder_name.startswith("native-n4-"):
        return folder_name.replace("native-n4-", "native-")
    elif folder_name.startswith("native-n16-"):
        return folder_name.replace("native-n16-", "native-overload-")
    return folder_name


def generer_graphes(df):
    """Generates scatter plots with linear trendlines and dynamic annotations."""
    os.makedirs("analysis", exist_ok=True)
    palette = {'seq': '#2E86AB', 'rand': '#A23B72'}
    
    print("\n--- [DEBUG] Plot Generation ---")
    
    # Helper to prevent overlapping labels on the IPC plot
    def get_ipc_style(scen_name):
        scen_lower = scen_name.lower()
        style = {
            'xytext': (12, 0),
            'ha': 'left',
            'va': 'center',
            'arrowprops': None
        }
        if 'native-n4-seq' in scen_lower:
            style.update({
                'xytext': (-30, -20), 'ha': 'right', 'va': 'top',
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=-0.1")
            })
        elif 'baseline-seq' in scen_lower:
            style.update({
                'xytext': (20, 20), 'ha': 'left', 'va': 'bottom',
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=0.1")
            })
        elif 'native-n4-rand' in scen_lower:
            style.update({
                'xytext': (-35, 15), 'ha': 'right', 'va': 'bottom',
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=0.1")
            })
        elif 'baseline-rand' in scen_lower:
            style.update({
                'xytext': (25, -25), 'ha': 'left', 'va': 'top',
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=-0.1")
            })
        return style

    # Helper to resolve overlaps on the MPKI plot
    def get_mpki_style(scen_name):
        scen_lower = scen_name.lower()
        style = {
            'xytext': (12, 0),
            'ha': 'left',
            'va': 'center',
            'arrowprops': None
        }
        # Avoid collisions for congested clusters
        if 'native-n4-seq' in scen_lower:
            style.update({
                'xytext': (-35, -25), 'ha': 'right', 'va': 'top',
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=-0.1")
            })
        elif 'baseline-seq' in scen_lower:
            style.update({
                'xytext': (30, -25), 'ha': 'left', 'va': 'top',  # Shifted downwards & right to clear extreme-seq
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=0.1")
            })
        elif 'extreme-seq' in scen_lower:
            style.update({
                'xytext': (20, 35), 'ha': 'left', 'va': 'bottom',  # Shifted upwards & right to avoid baseline-seq
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=-0.1")
            })
        elif 'native-n4-rand' in scen_lower:
            style.update({
                'xytext': (-45, 15), 'ha': 'right', 'va': 'bottom',
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=0.1")
            })
        elif 'baseline-rand' in scen_lower:
            style.update({
                'xytext': (30, -30), 'ha': 'left', 'va': 'top',
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=-0.1")
            })
        elif 'native-n16-rand' in scen_lower:
            style.update({
                'xytext': (25, 15), 'ha': 'left', 'va': 'bottom',
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=0.1")
            })
        elif 'extreme-rand' in scen_lower:
            style.update({
                'xytext': (25, -15), 'ha': 'left', 'va': 'top',
                'arrowprops': dict(arrowstyle="->", color="gray", lw=0.8, connectionstyle="arc3,rad=-0.1")
            })
        return style
    
    # ==========================================
    # PLOT 1: IPC vs Energy
    # ==========================================
    fig1, ax1 = plt.subplots(figsize=(12, 8))
    sns.scatterplot(data=df, x='ipc', y='nj_per_inst', hue='pattern', palette=palette, s=200, edgecolor='black', zorder=5, ax=ax1)
    
    print("[DEBUG] Placing IPC labels:")
    for index, row in df.iterrows():
        # Remove '-work' from the label string for cleaner text
        nom = str(row['scenario']).replace('-work', '')
        x_val = float(row['ipc'])
        y_val = float(row['nj_per_inst'])
        print(f"  -> Writing '{nom}' at coordinates X={x_val}, Y={y_val}")
        
        style = get_ipc_style(nom)
        
        ax1.annotate(nom, 
                     (x_val, y_val),
                     xytext=style['xytext'], 
                     textcoords='offset points',
                     ha=style['ha'],
                     va=style['va'],
                     arrowprops=style['arrowprops'],
                     fontsize=10, 
                     fontweight='bold', 
                     color='black',
                     bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.8", alpha=0.9, lw=1))

    # Draw sorted trendline
    if len(df) > 1:
        df_sorted_ipc = df.sort_values(by='ipc')
        z = np.polyfit(df_sorted_ipc['ipc'], df_sorted_ipc['nj_per_inst'], 1)
        ax1.plot(df_sorted_ipc['ipc'], np.poly1d(z)(df_sorted_ipc['ipc']), "r--", alpha=0.5, label='Trend')
        
    ax1.set_xlabel('Execution Efficiency (IPC)', fontweight='bold')
    ax1.set_ylabel('Actual Hardware Cost (nJ/inst)', fontweight='bold')
    ax1.set_title('Correlation: Impact of IPC on Energy Cost', fontweight='bold', fontsize=14)
    ax1.legend(title='Access Pattern')
    plt.tight_layout()
    fig1.savefig('analysis/analysis_approach1/correlation_ipc_complete.png', dpi=300)

    # ==========================================
    # PLOT 2: MPKI vs Energy
    # ==========================================
    if df['llc_mpki'].sum() > 0:
        fig2, ax2 = plt.subplots(figsize=(12, 8))
        sns.scatterplot(data=df, x='llc_mpki', y='nj_per_inst', hue='pattern', palette=palette, s=200, edgecolor='black', zorder=5, ax=ax2)
        
        print("\n[DEBUG] Placing MPKI labels:")
        for index, row in df.iterrows():
            nom = str(row['scenario']).replace('-work', '')
            x_val = float(row['llc_mpki'])
            y_val = float(row['nj_per_inst'])
            
            style = get_mpki_style(nom)
            
            ax2.annotate(nom, 
                         (x_val, y_val),
                         xytext=style['xytext'],
                         textcoords='offset points',
                         ha=style['ha'],
                         va=style['va'],
                         arrowprops=style['arrowprops'],
                         fontsize=10, 
                         fontweight='bold', 
                         color='black',
                         bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.8", alpha=0.9, lw=1))

        # Draw sorted trendline
        if len(df) > 1:
            df_sorted_mpki = df.sort_values(by='llc_mpki')
            z = np.polyfit(df_sorted_mpki['llc_mpki'], df_sorted_mpki['nj_per_inst'], 1)
            ax2.plot(df_sorted_mpki['llc_mpki'], np.poly1d(z)(df_sorted_mpki['llc_mpki']), "r--", alpha=0.5, label='Trend')
            
        ax2.set_xlabel('L3 Cache Misses per 1000 Instructions (MPKI)', fontweight='bold')
        ax2.set_ylabel('Actual Hardware Cost (nJ/inst)', fontweight='bold')
        ax2.set_title('Correlation: Impact of Memory Stalls on Energy', fontweight='bold', fontsize=14)
        ax2.legend(title='Access Pattern')
        plt.tight_layout()
        fig2.savefig('analysis/analysis_approach1/correlation_cache_mpki_complete.png', dpi=300)


def main():
    """The orchestrator that merges RAPL and PERF data."""
    print("=== Optimized Correlation Pipeline Started ===")
    
    # 1. Gather all baseline data using our robust local parser
    rapl_data = load_energy_medians_robust(RAPL_PATH)
    instructions_data = charger_dictionnaire_instructions(INSTRUCTIONS_FILE)
    
    if not rapl_data or not instructions_data:
        print("[ERROR] Missing essential data to proceed. Aborting.")
        return
        
    final_results = []
    scenario_folders = []
    
    # 2. Iterate through all specified performance directories
    for base_path in PERF_PATHS:
        if os.path.exists(base_path):
            folders = [d for d in glob.glob(os.path.join(base_path, "*")) if os.path.isdir(d)]
            scenario_folders.extend(folders)
        else:
            print(f"[Warning] Directory not found and will be skipped: {base_path}")
    
    # 3. Process each found folder
    for folder in scenario_folders:
        scenario_name = os.path.basename(folder).lower()
        
        # --- EXPLICIT USER FILTER ---
        # Only process requested native folders (N4 and N16), skip other core counts
        if scenario_name.startswith("native-"):
            if not (scenario_name.startswith("native-n4-") or scenario_name.startswith("native-n16-")):
                continue
        
        # Translate folder name to instructions key mapping
        inst_key = map_folder_to_instruction_key(scenario_name)
        
        # Verify matching entries exist
        if (scenario_name not in rapl_data) or (inst_key not in instructions_data):
            continue
            
        median_joules = rapl_data[scenario_name]
        total_instructions = instructions_data[inst_key]
        
        # Extract internal CPU metrics
        cache_metrics = extraire_metriques_microarchitecturales(folder)
        
        # 4. Calculate ultimate efficiency
        if cache_metrics and total_instructions > 0:
            nj_per_inst = (median_joules / total_instructions) * 1_000_000_000
            
            final_results.append({
                'scenario': scenario_name,
                'pattern': 'seq' if 'seq' in scenario_name else 'rand',
                'ipc': cache_metrics['ipc'],
                'llc_mpki': cache_metrics.get('llc_mpki', 0),
                'nj_per_inst': round(nj_per_inst, 2)
            })
            
    # 5. Save and Plot
    if final_results:
        df_final = pd.DataFrame(final_results)
        df_final.to_csv("exact_correlation_summary.csv", index=False)
        print("\n[SUCCESS] Summary saved in 'exact_correlation_summary.csv'")
        
        generer_graphes(df_final)
        print("[SUCCESS] Scientific plots generated in 'analysis/' folder")
    else:
        print("\n[ERROR] No matching data found to generate plots. Check naming conventions.")

if __name__ == "__main__":
    main()