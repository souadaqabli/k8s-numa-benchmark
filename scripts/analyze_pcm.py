#!/usr/bin/env python3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def analyze_pcm_memory(csv_path, scenario_name):
    """Reads a pcm-memory CSV and extracts key RAM metrics."""
    
    # 1. Read with MultiIndex to capture the 2 header rows
    df_raw = pd.read_csv(csv_path, header=[0, 1])
    
    # Merge the two rows to get a single column (e.g., "SKT0_MEM READ (MB/S)")
    df_raw.columns = [f"{str(c[0]).strip().upper()}_{str(c[1]).strip().upper()}" for c in df_raw.columns]
    cols = df_raw.columns.tolist()
    
    # 2. CORRECTED DETECTION: Specifically target "MEM READ/WRITE"
    skt0_read_col = [c for c in cols if 'SKT0' in c and 'MEM READ' in c]
    skt0_write_col = [c for c in cols if 'SKT0' in c and 'MEM WRITE' in c]
    skt1_read_col = [c for c in cols if 'SKT1' in c and 'MEM READ' in c]
    skt1_write_col = [c for c in cols if 'SKT1' in c and 'MEM WRITE' in c]

    # 3. Safe extraction (converts to numeric)
    skt0_read = pd.to_numeric(df_raw[skt0_read_col[0]], errors='coerce').fillna(0) if skt0_read_col else pd.Series([0.0]*len(df_raw))
    skt0_write = pd.to_numeric(df_raw[skt0_write_col[0]], errors='coerce').fillna(0) if skt0_write_col else pd.Series([0.0]*len(df_raw))
    skt1_read = pd.to_numeric(df_raw[skt1_read_col[0]], errors='coerce').fillna(0) if skt1_read_col else pd.Series([0.0]*len(df_raw))
    skt1_write = pd.to_numeric(df_raw[skt1_write_col[0]], errors='coerce').fillna(0) if skt1_write_col else pd.Series([0.0]*len(df_raw))
    
    # 4. Conversion: PCM exports in MB/s here -> Divide by 1000 to get GB/s
    skt0_read_gbs = skt0_read / 1000.0
    skt0_write_gbs = skt0_write / 1000.0
    skt1_read_gbs = skt1_read / 1000.0
    skt1_write_gbs = skt1_write / 1000.0
    
    skt0_total_gbs = skt0_read_gbs + skt0_write_gbs
    skt1_total_gbs = skt1_read_gbs + skt1_write_gbs
    
    # 5. Statistical calculations
    results = {
        'scenario': scenario_name,
        'duration_sec': len(df_raw),
        'skt0_read_mean': float(np.nanmean(skt0_read_gbs)),
        'skt0_write_mean': float(np.nanmean(skt0_write_gbs)),
        'skt0_total_mean': float(np.nanmean(skt0_total_gbs)),
        'skt0_total_max': float(np.nanmax(skt0_total_gbs)),
        'skt0_read_std': float(np.nanstd(skt0_read_gbs)),
        'skt1_read_mean': float(np.nanmean(skt1_read_gbs)),
        'skt1_write_mean': float(np.nanmean(skt1_write_gbs)),
        'skt1_total_mean': float(np.nanmean(skt1_total_gbs)),
        'system_total_mean': float(np.nanmean(skt0_total_gbs + skt1_total_gbs)),
        'system_total_max': float(np.nanmax(skt0_total_gbs + skt1_total_gbs)),
    }
    
    # 6. Estimated occupancy
    theoretical_max = 25.6  # GB/s per socket
    results['skt0_occupancy_pct'] = (results['skt0_total_mean'] / theoretical_max) * 100
    results['skt0_peak_occupancy_pct'] = (results['skt0_total_max'] / theoretical_max) * 100
    
    return results, df_raw, skt0_total_gbs, skt1_total_gbs

# === ANALYSIS ===
print("=" * 60)
print("PCM-MEMORY ANALYSIS: Extreme Rand N10 vs N12")
print("=" * 60)

r10, df10, s0_10, s1_10 = analyze_pcm_memory(
    "/home/sdnuser/pcm_mem_extreme_n10_rand.csv", 
    "Extreme-Rand-N10"
)

r12, df12, s0_12, s1_12 = analyze_pcm_memory(
    "/home/sdnuser/pcm_mem_extreme_n12_rand.csv", 
    "Extreme-Rand-N12"
)

# Comparative Table
print("\n" + "=" * 60)
print("COMPARATIVE TABLE")
print("=" * 60)
print(f"{'Metric':<35} {'N10':>12} {'N12':>12}")
print("-" * 60)
print(f"{'Sampled duration (s)':<35} {r10['duration_sec']:>12} {r12['duration_sec']:>12}")
print(f"{'SKT0 Read (GB/s)':<35} {r10['skt0_read_mean']:>12.2f} {r12['skt0_read_mean']:>12.2f}")
print(f"{'SKT0 Write (GB/s)':<35} {r10['skt0_write_mean']:>12.2f} {r12['skt0_write_mean']:>12.2f}")
print(f"{'SKT0 Total (GB/s)':<35} {r10['skt0_total_mean']:>12.2f} {r12['skt0_total_mean']:>12.2f}")
print(f"{'SKT0 Peak Total (GB/s)':<35} {r10['skt0_total_max']:>12.2f} {r12['skt0_total_max']:>12.2f}")
print(f"{'SKT0 Average Occupancy (%)':<35} {r10['skt0_occupancy_pct']:>12.1f} {r12['skt0_occupancy_pct']:>12.1f}")
print(f"{'SKT0 Peak Occupancy (%)':<35} {r10['skt0_peak_occupancy_pct']:>12.1f} {r12['skt0_peak_occupancy_pct']:>12.1f}")
print(f"{'SKT1 Total (GB/s)':<35} {r10['skt1_total_mean']:>12.2f} {r12['skt1_total_mean']:>12.2f}")
print(f"{'System Total (GB/s)':<35} {r10['system_total_mean']:>12.2f} {r12['system_total_mean']:>12.2f}")

# Interpretation
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

if r12['skt0_occupancy_pct'] > 85:
    print(" EVIDENCE: Socket 0 memory controller is SATURATED at N12")
    print(f"   Average occupancy: {r12['skt0_occupancy_pct']:.1f}%")
else:
    print("  SKT0 occupancy below 85%")

if r12['skt1_total_mean'] < r12['skt0_total_mean'] * 0.1:
    print(" EVIDENCE: Socket 1 is INACTIVE (all traffic on Socket 0)")
    print(f"   SKT1/SKT0 ratio: {r12['skt1_total_mean']/r12['skt0_total_mean']*100:.1f}%")

if r12['skt0_total_mean'] > r10['skt0_total_mean'] * 1.1:
    print(" N12 bandwidth > N10 (more pods requesting more bandwidth)")
elif abs(r12['skt0_total_mean'] - r10['skt0_total_mean']) < 2:
    print(" EVIDENCE: BOTTLENECK / CAPPING. N12 does not increase bandwidth")
    print("   The controller is at its physical limit.")
else:
    print(f"   Bandwidth evolution: {r10['skt0_total_mean']:.2f} → {r12['skt0_total_mean']:.2f} GB/s")

# Graphing
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1. SKT0 Bandwidth over time
ax = axes[0, 0]
ax.plot(s0_10, label='N10', color='#2E86AB', linewidth=2)
ax.plot(s0_12, label='N12', color='#A23B72', linewidth=2)
ax.axhline(25.6, color='red', linestyle='--', alpha=0.5, label='Theoretical max (25.6 GB/s)')
ax.set_title('Socket 0 DRAM Bandwidth')
ax.set_ylabel('GB/s')
ax.set_xlabel('Time (s)')
ax.legend()
ax.grid(True, alpha=0.3)

# 2. Average comparison SKT0 vs SKT1
ax = axes[0, 1]
x = ['N10 SKT0', 'N10 SKT1', 'N12 SKT0', 'N12 SKT1']
vals = [r10['skt0_total_mean'], r10['skt1_total_mean'], r12['skt0_total_mean'], r12['skt1_total_mean']]
colors = ['#2E86AB', '#2E86AB', '#A23B72', '#A23B72']
bars = ax.bar(x, vals, color=colors, alpha=0.8, edgecolor='black')
ax.axhline(25.6, color='red', linestyle='--', alpha=0.5, label='Theoretical max')
ax.set_title('Bandwidth per Socket')
ax.set_ylabel('GB/s')
for bar, val in zip(bars, vals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
            f'{val:.1f}', ha='center', va='bottom', fontweight='bold')
ax.legend()

# 3. Estimated occupancy
ax = axes[1, 0]
occ = [r10['skt0_occupancy_pct'], r12['skt0_occupancy_pct']]
bars = ax.bar(['N10', 'N12'], occ, color=['#2E86AB', '#A23B72'], edgecolor='black')
ax.axhline(100, color='red', linestyle='--', alpha=0.5, label='Saturation (100%)')
ax.set_title('Estimated Socket 0 Controller Occupancy')
ax.set_ylabel('% of theoretical bandwidth')
for bar, val in zip(bars, occ):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
            f'{val:.1f}%', ha='center', va='bottom', fontweight='bold')
ax.legend()

# 4. Temporal distribution (histogram)
ax = axes[1, 1]
ax.hist(s0_10, bins=30, alpha=0.6, label='N10', color='#2E86AB')
ax.hist(s0_12, bins=30, alpha=0.6, label='N12', color='#A23B72')
ax.set_title('SKT0 Bandwidth Distribution')
ax.set_xlabel('GB/s')
ax.set_ylabel('Frequency')
ax.legend()

plt.tight_layout()
plt.savefig('pcm_analysis_n10_vs_n12.png', dpi=300, bbox_inches='tight')
print("\nGraph saved: pcm_analysis_n10_vs_n12.png")