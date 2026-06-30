import pandas as pd
import os

def get_energy_medians(rapl_csv_path):
    """
    Reads the RAPL file, groups by scenario, and calculates the median energy.
    Returns a dictionary: { 'scenario_name': total_median_joules }
    """
    if not os.path.exists(rapl_csv_path):
        print(f"[ERROR] RAPL file not found: {rapl_csv_path}")
        return {}

    # Safe CSV reading
    cols = ['scenario', 'status', 'time', 'energy_total', 'pkg0', 'pkg1', 'dram0', 'dram1']
    df = pd.read_csv(rapl_csv_path, names=cols, skiprows=1)
    
    # Clean names (lowercase, strip whitespaces)
    df['scenario'] = df['scenario'].astype(str).str.strip().str.lower()
    
    # Convert micro-Joules to Joules
    df['pkg0_j'] = pd.to_numeric(df['pkg0'], errors='coerce') / 1_000_000
    df['pkg1_j'] = pd.to_numeric(df['pkg1'], errors='coerce') / 1_000_000
    df['dram0_j'] = pd.to_numeric(df['dram0'], errors='coerce') / 1_000_000
    df['dram1_j'] = pd.to_numeric(df['dram1'], errors='coerce') / 1_000_000
    
    # Total hardware energy (CPU + RAM)
    df['total_joules'] = df['pkg0_j'] + df['pkg1_j'] + df['dram0_j'] + df['dram1_j']

    # Extract the Median to eliminate OS Jitter (outliers)
    df_median = df.groupby('scenario')[['total_joules']].median().reset_index()
    
    # Create the output dictionary
    rapl_dict = {row['scenario']: row['total_joules'] for _, row in df_median.iterrows()}
    
    print(f"[parser_rapl] {len(rapl_dict)} unique scenarios smoothed via median.")
    return rapl_dict