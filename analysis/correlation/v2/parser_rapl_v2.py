import os
import pandas as pd
import statistics

def get_energy_medians_v2(csv_path):
    """
    Reads the Approach 2 RAPL CSV file, constructs unified keys,
    and computes the median energy in Joules for each unique configuration.
    """
    if not os.path.exists(csv_path):
        print(f"[ERROR] RAPL CSV file not found at: {csv_path}")
        return {}

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"[ERROR] Failed to read RAPL CSV file. Reason: {e}")
        return {}

    raw_energy_data = {}

    # Step 1: Group microJoules values by the Unified Key
    for index, row in df.iterrows():
        try:
            # Clean and standardize strings to build a deterministic key
            pattern = str(row['pattern']).strip().lower()       # e.g., 'seq' or 'rand'
            cores = str(row['cores']).strip().lower()           # e.g., 'n4', 'n6', etc.
            scenario_raw = str(row['scenario']).strip().lower() # e.g., 'baseline', 'extreme'
            
            # Construct the Unified Key matching the performance parser output
            unified_key = f"{scenario_raw}-{cores}-{pattern}"
            
            # Convert microJoules (uJ) to Joules (J)
            energy_joules = float(row['total_uj']) / 1_000_000.0
            
            if unified_key not in raw_energy_data:
                raw_energy_data[unified_key] = []
                
            raw_energy_data[unified_key].append(energy_joules)
            
        except KeyError as e:
            print(f"[ERROR] Missing expected column in RAPL CSV: {e}")
            return {}
        except Exception as e:
            print(f"[WARNING] Skipping row {index} due to unexpected error: {e}")

    # Step 2: Compute the statistical median for each unified configuration
    final_energy_medians = {}
    for key, values in raw_energy_data.items():
        final_energy_medians[key] = statistics.median(values)
        
    print(f"[SUCCESS] Parsed RAPL data. Generated {len(final_energy_medians)} unique configuration medians.")
    return final_energy_medians

if __name__ == "__main__":
    # Standalone verification block
    SAMPLE_PATH = "results/RAPL/scalability_energy_results_complete.csv"
    print(f"--- Testing parser_rapl_v2 with path: {SAMPLE_PATH} ---")
    
    medians = get_energy_medians_v2(SAMPLE_PATH)
    for key, value in list(medians.items())[:5]:
        print(f"  -> {key}: {value:.4f} Joules")