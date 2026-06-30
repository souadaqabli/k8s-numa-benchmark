import pandas as pd
import os

# --- 1. Load the data ---
csv_path = "results/RAPL/scalability_energy_results_complete.csv"
if not os.path.exists(csv_path):
    print(f"Error: File {csv_path} not found.")
    exit(1)

df = pd.read_csv(csv_path)

# Convert micro-Joules to Joules
df['total_joules'] = df['total_uj'] / 1_000_000

# Extract the number of cores (N4 -> 4) and calculate Volume (10 GB per pod)
df['num_cores'] = df['cores'].astype(str).str.replace('N', '').astype(int)
df['volume_gb'] = df['num_cores'] * 10

# Ensure correct display order for cores
df['cores'] = pd.Categorical(df['cores'], categories=['N4', 'N6', 'N8', 'N10', 'N12'], ordered=True)

# --- 2. Calculate Medians ---
# Group by Pattern, Cores, and Scenario, then calculate the median for Time and Energy
table_data = df.groupby(['pattern', 'cores', 'scenario'], observed=False).agg(
    volume_gb=('volume_gb', 'first'),              
    median_time_s=('duration_s', 'median'),        
    median_energy_j=('total_joules', 'median')     
).dropna().reset_index()

# --- 3. NORMALIZATION (Throughput and Efficiency) ---
table_data['throughput_gb_s'] = table_data['volume_gb'] / table_data['median_time_s']
table_data['efficiency_j_gb'] = table_data['median_energy_j'] / table_data['volume_gb']

# --- 4. Formatting ---
table_data['median_time_s'] = table_data['median_time_s'].round(0).astype(int)
table_data['median_energy_j'] = table_data['median_energy_j'].round(0).astype(int)
table_data['throughput_gb_s'] = table_data['throughput_gb_s'].round(3)
table_data['efficiency_j_gb'] = table_data['efficiency_j_gb'].round(0).astype(int)

table_data = table_data.rename(columns={
    'pattern': 'Access Pattern',
    'cores': 'Pods/Cores',
    'scenario': 'NUMA Scenario',
    'volume_gb': 'Total Volume (GB)',
    'median_time_s': 'Median Time (s)',
    'median_energy_j': 'Median Energy (Joules)',
    'throughput_gb_s': 'Throughput (GB/s)',
    'efficiency_j_gb': 'Efficiency (Joules/GB)'
})

# --- 5. SPLITTING INTO TWO TABLES ---
# Create distinct DataFrames for Sequential and Random patterns
table_seq = table_data[table_data['Access Pattern'] == 'seq'].copy()
table_rand = table_data[table_data['Access Pattern'] == 'rand'].copy()

# Sort logically for each table (By core count, then by scenario)
table_seq = table_seq.sort_values(by=['Pods/Cores', 'NUMA Scenario'])
table_rand = table_rand.sort_values(by=['Pods/Cores', 'NUMA Scenario'])

# --- 6. EXPORT AND DISPLAY ---
os.makedirs("analysis", exist_ok=True)
output_csv_seq = "analysis/normalized_table_seq.csv"
output_csv_rand = "analysis/normalized_table_rand.csv"

# Save to CSV
table_seq.to_csv(output_csv_seq, index=False)
table_rand.to_csv(output_csv_rand, index=False)

print(f" SEQUENTIAL file saved: {output_csv_seq}")
print(f" RANDOM file saved: {output_csv_rand}")

# Display Markdown (Removing the 'Access Pattern' column as it's now redundant)
print("\n=========================================================================================")
print("                      TABLE 1: SEQUENTIAL ACCESS (SEQ)")
print("=========================================================================================")
print(table_seq.drop(columns=['Access Pattern']).to_markdown(index=False))

print("\n\n=========================================================================================")
print("                      TABLE 2: RANDOM ACCESS (RAND)")
print("=========================================================================================")
print(table_rand.drop(columns=['Access Pattern']).to_markdown(index=False))
print("\n")