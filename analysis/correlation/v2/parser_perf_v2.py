import os
import glob
import pandas as pd

def parse_folder_name(folder_name):
    prefix = folder_name.split('_')[0] 
    parts = prefix.split('-')
    
    scenario_map = {
        "base": "baseline",
        "extr": "extreme",
        "cross": "cross-numa",
        "excr": "extreme-cross"
    }
    
    if len(parts) >= 4 and parts[0] == "bench":
        scenario_abbrev = parts[1]
        scenario = scenario_map.get(scenario_abbrev, "unknown")
        pattern = parts[-1]     
        
        cores = None
        for p in parts:
            if p.startswith('n') and p[1:].isdigit():
                cores = p
                break
                
        if cores and pattern in ['seq', 'rand']:
            unified_key = f"{scenario}-{cores}-{pattern}"
            return unified_key
            
    return None

def extract_massive_micro_metrics(base_directory):
    print("[INFO] Starting massive performance data aggregation...")
    
    global_metrics = {}
    search_pattern = os.path.join(base_directory, "**", "*.csv")
    all_csv_files = glob.glob(search_pattern, recursive=True)
    
    if not all_csv_files:
        print(f"[ERROR] No CSV files found in {base_directory}")
        return {}

    for file_path in all_csv_files:
        parent_dir = os.path.basename(os.path.dirname(file_path))
        unified_key = parse_folder_name(parent_dir)
        
        if not unified_key:
            continue
            
        if unified_key not in global_metrics:
            global_metrics[unified_key] = {
                "total_cycles": 0.0,
                "total_instructions": 0.0,
                "total_llc_misses": 0.0,
                "dir_count": 0  # We count POD directories, not runs
            }
            
        try:
            df = pd.read_csv(file_path)
            
            if 'IPC' in df.columns and 'cycles' in df.columns:
                global_metrics[unified_key]["total_cycles"] += df['cycles'].sum()
                global_metrics[unified_key]["total_instructions"] += (df['IPC'] * df['cycles']).sum()
                
            if 'LLC_misses' in df.columns:
                global_metrics[unified_key]["total_llc_misses"] += df['LLC_misses'].sum()
                
            # Successfully parsed one pod's directory
            global_metrics[unified_key]["dir_count"] += 1
            
        except Exception:
            pass

    final_results = {}
    
    for key, metrics in global_metrics.items():
        dir_count = metrics["dir_count"]
        
        # Extract the N value from the key (e.g., 'baseline-n4-seq' -> 4)
        parts = key.split('-')
        cores_str = parts[-2]
        N = int(cores_str.replace('n', ''))
        
        if dir_count > 0 and metrics["total_cycles"] > 0 and metrics["total_instructions"] > 0:
            
            # --- THE KUBERNETES POD MATH FIX ---
            # Total actual physical runs = (Number of pod directories) / (Pods per run)
            actual_runs = dir_count / N
            
            # Average instructions for ONE complete server run
            avg_instructions_per_run = metrics["total_instructions"] / actual_runs
            
            # Global metrics remain ratio-based across all data for highest accuracy
            global_ipc = metrics["total_instructions"] / metrics["total_cycles"]
            global_mpki = (metrics["total_llc_misses"] / metrics["total_instructions"]) * 1000
            
            final_results[key] = {
                "ipc": round(global_ipc, 3),
                "llc_mpki": round(global_mpki, 2),
                "total_instructions": avg_instructions_per_run,
                "parsed_dirs": dir_count,
                "calculated_runs": actual_runs
            }
            
    print(f"[SUCCESS] Aggregated metrics for {len(final_results)} unique scenarios.")
    return final_results