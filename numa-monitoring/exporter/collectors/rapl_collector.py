import os
import time
import metrics

# Format: { 'domain_name': (energy_uj, timestamp_seconds) }
_previous_state = {}
# Cache to store the dynamic max range of each CPU to avoid reading the file every 5 seconds
# Format: { 'domain_name': max_energy_uj }
_max_energy_ranges = {}

# Explicit whitelist of the RAPL domains to sum: PKG (whole socket) + DRAM,
# for both sockets. /sys/class/powercap/ also exposes intel-rapl:X:0 ("core"
# sub-domains), which are a SUBSET of intel-rapl:X (already included in the
# PKG reading) -- summing them too would double-count CPU energy. This
# mirrors exactly the 4 paths read by the manual RAPL campaign script
# (intel-rapl:0, intel-rapl:0:1=dram0, intel-rapl:1, intel-rapl:1:1=dram1).
VALID_DOMAINS = {'intel-rapl:0', 'intel-rapl:0:1', 'intel-rapl:1', 'intel-rapl:1:1'}


def collect_rapl():
    """
    Reads hardware RAPL energy counters and computes power consumption in Watts.
    Dynamically reads max_energy_range_uj to accurately handle hardware wraparound.

    Returns the total energy delta (in uJ, summed across the 4 valid RAPL
    domains: PKG0, DRAM0, PKG1, DRAM1) consumed since the last call, so the
    caller (main.py) can accumulate it over the duration of a full run ->
    nJ/instruction is then computed as total_run_energy / total_run_instructions,
    the same method already validated manually in
    generate_matmul_energy_efficiency_tables.py.
    """
    total_delta_uj = 0.0
    try:
        base_dir = '/sys/class/powercap/'
        if not os.path.exists(base_dir):
            return total_delta_uj

        # Only iterate over the 4 valid domains (PKG0, DRAM0, PKG1, DRAM1) --
        # NOT every folder starting with 'intel-rapl:', which would also
        # match the 'core' sub-domains (intel-rapl:0:0, intel-rapl:1:0) and
        # double-count energy already included in the PKG reading.
        for domain in VALID_DOMAINS:
            energy_file = os.path.join(base_dir, domain, 'energy_uj')
            max_file = os.path.join(base_dir, domain, 'max_energy_range_uj')

            if os.path.exists(energy_file):

                # 1. Dynamically read and cache the max range for this specific CPU
                if domain not in _max_energy_ranges:
                    if os.path.exists(max_file):
                        with open(max_file, 'r') as mf:
                            _max_energy_ranges[domain] = float(mf.read().strip())
                    else:
                        # Fallback just in case the OS blocks access to the max file
                        _max_energy_ranges[domain] = 65532610987.0

                # 2. Read current energy
                with open(energy_file, 'r') as f:
                    current_energy_uj = float(f.read().strip())

                current_time = time.time()

                # 3. Calculate Watts (and accumulate the energy delta)
                if domain in _previous_state:
                    prev_energy_uj, prev_time = _previous_state[domain]
                    time_delta = current_time - prev_time

                    if time_delta > 0:
                        energy_delta_uj = current_energy_uj - prev_energy_uj

                        # Handle hardware wraparound using the dynamic max limit
                        if energy_delta_uj < 0:
                            energy_delta_uj += _max_energy_ranges[domain]

                        power_watts = (energy_delta_uj / 1_000_000.0) / time_delta
                        metrics.RAPL_POWER.labels(domain=domain).set(power_watts)

                        # Accumulate this domain's energy delta into the total
                        total_delta_uj += energy_delta_uj

                _previous_state[domain] = (current_energy_uj, current_time)

    except Exception as e:
        print(f"[RAPL Collector] Error reading power metrics: {e}")
    return total_delta_uj
