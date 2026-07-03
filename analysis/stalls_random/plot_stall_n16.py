#!/usr/bin/env python3
"""
plot_stall_n16.py

Plots the temporal evolution of memory stall rate for Native Overload N16 random.
Shows that 74% of CPU cycles are spent stalling on memory throughout execution,
proving that the nJ/inst improvement is due to CPU idling, not efficiency.
"""

import os
import re
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

INPUT  = os.path.expanduser("~/k8s-numa-benchmark/results/stalls/native_n16_rand_system_3.txt")
OUTPUT = "analysis/stall_rate_n16_rand_decalage.png"


def parse_perf(path):
    records = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = re.match(r'(\d+\.\d+)\s+([\d,]+|<not counted>)\s+(\S+)', line)
            if not m:
                continue
            ts    = float(m.group(1))
            count = m.group(2)
            if count == '<not counted>':
                continue
            value = int(count.replace(',', ''))

            parts = line.split()
            event = None
            for p in parts[2:]:
                if p.startswith('cycle') or p == 'cycles' or p == 'instructions':
                    event = p
                    break
                if re.match(r'^[a-z_]', p) and p not in ('#', 'insn', 'per', 'unit'):
                    event = p
                    break
            if event is None:
                continue

            if ts not in records:
                records[ts] = {}
            records[ts][event] = value

    rows = []
    for ts in sorted(records.keys()):
        r = records[ts]
        cyc   = r.get('cycles', 0)
        instr = r.get('instructions', 0)
        s_mem = r.get('cycle_activity.stalls_mem_any', 0)
        s_tot = r.get('cycle_activity.stalls_total', 0)
        s_nex = r.get('cycle_activity.cycles_no_execute', 0)
        if cyc == 0:
            continue
        rows.append({
            't':          ts,
            'ipc':        instr / cyc,
            'stall_mem':  s_mem / cyc * 100,   # percentage
            'stall_tot':  s_tot / cyc * 100,
            'no_execute': s_nex / cyc * 100,
        })

    t     = np.array([r['t'] for r in rows])
    t     = t - t[0]   # normalize to 0
    ipc   = np.array([r['ipc'] for r in rows])
    smem  = np.array([r['stall_mem'] for r in rows])
    stot  = np.array([r['stall_tot'] for r in rows])
    noex  = np.array([r['no_execute'] for r in rows])

    return t, ipc, smem, stot, noex


def smooth(arr, window=7):
    return np.convolve(arr, np.ones(window)/window, mode='same')


t, ipc, smem, stot, noex = parse_perf(INPUT)

print(f"Loaded {len(t)} samples over {t[-1]:.0f}s")
print(f"Mean IPC            : {np.mean(ipc):.3f}")
print(f"Mean stall_mem      : {np.mean(smem):.1f}%")
print(f"Mean stall_total    : {np.mean(stot):.1f}%")
print(f"Mean cycles_no_exec : {np.mean(noex):.1f}%")

# ── Plot ──
os.makedirs("analysis", exist_ok=True)
fig = plt.figure(figsize=(14, 10))
gs  = gridspec.GridSpec(3, 1, hspace=0.35)

# ── Panel 1: IPC ──
ax1 = fig.add_subplot(gs[0])
ax1.plot(t, smooth(ipc), color='#2471a3', linewidth=1.5, alpha=0.9, label='IPC')
ax1.axhline(np.mean(ipc), color='#2471a3', linestyle='--', linewidth=1.2,
            label=f'Mean IPC = {np.mean(ipc):.3f}')
ax1.set_ylabel('IPC', fontsize=11)
ax1.set_title('Native Overload N16 Random — CPU Activity Over Time',
              fontsize=13, fontweight='bold')
ax1.legend(fontsize=9, loc='upper right')
ax1.set_ylim(bottom=0)
ax1.grid(True, alpha=0.25)
ax1.text(0.02, 0.95,
         'IPC < 0.2 means the CPU executes\nless than 1 instruction every 5 cycles',
         transform=ax1.transAxes, fontsize=8, va='top', color='gray',
         bbox=dict(boxstyle='round', facecolor='white', alpha=0.6))

# ── Panel 2: Memory stall rate ──
ax2 = fig.add_subplot(gs[1])
ax2.fill_between(t, 0, smooth(smem), alpha=0.3, color='#e74c3c')
ax2.plot(t, smooth(smem), color='#e74c3c', linewidth=1.5, alpha=0.9,
         label='Memory stall rate')
ax2.axhline(np.mean(smem), color='#c0392b', linestyle='--', linewidth=1.2,
            label=f'Mean = {np.mean(smem):.1f}% of cycles')
ax2.axhline(50, color='gray', linestyle=':', linewidth=1, alpha=0.5)
ax2.text(t[-1]*0.98, 52, '50%', ha='right', color='gray', fontsize=8)
ax2.set_ylabel('Memory Stall Rate (%)\ncycle_activity.stalls_mem_any / cycles',
               fontsize=10)
ax2.legend(fontsize=9, loc='upper right')
ax2.set_ylim(0, max(smooth(smem)) * 1.15)
ax2.grid(True, alpha=0.25)

# Key insight annotation
ax2.annotate(
    f'{np.mean(smem):.0f}% of CPU cycles\nspent waiting for memory',
    xy=(t[len(t)//2], np.mean(smem)),
    xytext=(t[len(t)//3], np.mean(smem) * 1.25),
    fontsize=11, fontweight='bold', color='#c0392b',
    arrowprops=dict(arrowstyle='->', color='#c0392b', lw=1.5),
    bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8)
)

# ── Panel 3: Total stall rate ──
ax3 = fig.add_subplot(gs[2])
ax3.fill_between(t, 0, smooth(stot), alpha=0.2, color='#8e44ad')
ax3.plot(t, smooth(stot), color='#8e44ad', linewidth=1.5, alpha=0.9,
         label='Total stall rate')
ax3.fill_between(t, 0, smooth(smem), alpha=0.2, color='#e74c3c')
ax3.plot(t, smooth(smem), color='#e74c3c', linewidth=1.2, alpha=0.7,
         label='Memory stalls (subset)')
ax3.axhline(np.mean(stot), color='#6c3483', linestyle='--', linewidth=1.2,
            label=f'Mean total = {np.mean(stot):.1f}%')
ax3.set_ylabel('Total Stall Rate (%)\ncycle_activity.stalls_total / cycles',
               fontsize=10)
ax3.set_xlabel('Time (seconds)', fontsize=11)
ax3.legend(fontsize=9, loc='upper right')
ax3.set_ylim(0, max(smooth(stot)) * 1.15)
ax3.grid(True, alpha=0.25)

# Memory fraction of total stalls
mem_fraction = np.mean(smem) / np.mean(stot) * 100
ax3.text(0.02, 0.95,
         f'Memory stalls = {mem_fraction:.0f}% of all stalls\n'
         f'→ Memory subsystem is the dominant bottleneck',
         transform=ax3.transAxes, fontsize=9, va='top',
         bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))

plt.savefig(OUTPUT, dpi=150, bbox_inches='tight')
print(f"\n[OK] Plot saved: {OUTPUT}")
plt.close()

# ── Summary for report ──
print(f"""
{'='*55}
  KEY FINDINGS FOR REPORT
{'='*55}

  Under Native Overload N=16 random access:

    Mean IPC             = {np.mean(ipc):.3f}
    Memory stall rate    = {np.mean(smem):.1f}% of all CPU cycles
    Total stall rate     = {np.mean(stot):.1f}% of all CPU cycles
    Memory stalls share  = {mem_fraction:.0f}% of all stalls

  The CPU spends {np.mean(smem):.0f}% of its cycles waiting for memory.
  This explains why nJ/instruction decreases (-53%):
  the CPU consumes less dynamic power (it is not computing),
  while execution time increases (+53%).
  The apparent efficiency gain is CPU idling, not real efficiency.
""")