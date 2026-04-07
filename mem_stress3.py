#!/usr/bin/env python3
# mem_stress3.py -
import numpy as np
import time
import os
import argparse

# ============================================================================
# CALIBRATION (Run ONCE at startup)
# ============================================================================

N_calibration = 1_000_000

# 1. Measuring time.perf_counter_ns() overhead
total_overhead = 0
for i in range(N_calibration):
    Tstart = time.perf_counter_ns()
    Tend = time.perf_counter_ns()
    total_overhead += (Tend - Tstart)

timeperf = total_overhead / N_calibration  
print(f"[CALIBRATION] Overhead time.perf_counter_ns() : {timeperf:.2f} ns")

# 2. Measuring .sum() overhead on an empty array
total_sum_overhead = 0
a = np.array([], dtype=np.uint64) 
result = np.zeros((), dtype=np.uint64)

for i in range(N_calibration):
    t_init = time.perf_counter_ns()
    a.sum(out=result)
    t_final = time.perf_counter_ns()
    total_sum_overhead += (t_final - t_init)

time_sum = total_sum_overhead / N_calibration  
print(f"[CALIBRATION] Overhead .sum() : {time_sum:.2f} ns")
print(f"[CALIBRATION] Overhead total (read) : {timeperf + time_sum:.2f} ns")
print(f"[CALIBRATION] Overhead total (write) : {timeperf:.2f} ns\n")

# ============================================================================
# SEQUENTIAL READ (Corrected Version)
# ============================================================================

def sequential_read(size_bytes, iterations):
    """
    Benchmarks sequential memory read performance (linear access).
    
    Args:
        size_bytes: Array size in bytes
        iterations: Number of repetitions
    
    Returns:
        (gb_s, duration, avg_lat_ns, min_ns, max_ns, avg_lat_iter, 
         min_lat_iter, max_lat_iter, std_per_element, all_latencies)
    """
    size = size_bytes // 8  # Nombre d'éléments float64
    src = np.ones(size, dtype=np.uint64)  # ← Type cohérent
    result = np.zeros((), dtype=np.uint64)
    
    all_latencies_raw = []  
    
    # Chronométrage PURE de l'opération (sans calculs statistiques)
    t_start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        src.sum(out=result)
        t1 = time.perf_counter_ns()
        all_latencies_raw.append(t1 - t0)  
    t_end = time.perf_counter()
    
    # ========================================================================
    # Statistical calculations AFTER timing (avoids pollution)
    # ========================================================================
    
    stat = np.zeros(4, dtype=np.float64)  
    stat[0] = np.inf  # Min
    stat[1] = -np.inf  # Max
    # stat[2] = sum
    # stat[3] = sum of squares
    
    overhead = (timeperf + time_sum) 
    
    for lat_raw in all_latencies_raw:
        lat = lat_raw - overhead
        stat[0] = min(stat[0], lat)
        stat[1] = max(stat[1], lat)
        stat[2] += lat
        stat[3] += lat**2
    
    # ========================================================================
    # Final calculations
    # ========================================================================
    
    # Débit (bandwidth)
    bytes_processed = size_bytes * iterations
    gb_s = bytes_processed / (t_end - t_start) / (1024**3)
    
    # Latence par itération (temps pour lire TOUT le tableau une fois)
    avg_lat_iter = stat[2] / iterations
    min_lat_iter = stat[0]
    max_lat_iter = stat[1]
    
    # Latence par élément (temps moyen pour lire UN élément)
    avg_lat_ns = avg_lat_iter / size
    min_ns = min_lat_iter / size
    max_ns = max_lat_iter / size
    
    # Écart-type
    variance = (stat[3] / iterations) - (avg_lat_iter**2)
    std = np.sqrt(max(0, variance))
    std_per_element = std / size
    
    return (gb_s, t_end - t_start, avg_lat_ns, min_ns, max_ns, 
            avg_lat_iter, min_lat_iter, max_lat_iter, 
            std_per_element, all_latencies_raw)


# ============================================================================
# SEQUENTIAL WRITE (Corrected Version)
# ============================================================================

def sequential_write(size_bytes, iterations):
    """
    Benchmarks sequential memory write performance (linear fill).
    
    Args:
        size_bytes: Array size in bytes
        iterations: Number of repetitions
    
    Returns:
        (gb_s, duration, avg_lat_ns, min_ns, max_ns, avg_lat_iter, 
         min_lat_iter, max_lat_iter, std_per_element, all_latencies)
    """
    size = size_bytes // 8
    arr = np.zeros(size, dtype=np.uint64)  
    
    all_latencies_raw = []
    
    t_start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        arr[:] = 1  
        t1 = time.perf_counter_ns()
        all_latencies_raw.append(t1 - t0)
    t_end = time.perf_counter()
    
    # Statistics
    stat = np.zeros(4, dtype=np.float64)
    stat[0] = np.inf
    stat[1] = -np.inf
    
    overhead = timeperf 
    
    for lat_raw in all_latencies_raw:
        lat = lat_raw - overhead
        stat[0] = min(stat[0], lat)
        stat[1] = max(stat[1], lat)
        stat[2] += lat
        stat[3] += lat**2
    
    # Calculations
    bytes_processed = size_bytes * iterations
    gb_s = bytes_processed / (t_end - t_start) / (1024**3)
    
    avg_lat_iter = stat[2] / iterations
    min_lat_iter = stat[0]
    max_lat_iter = stat[1]
    
    avg_lat_ns = avg_lat_iter / size
    min_ns = min_lat_iter / size
    max_ns = max_lat_iter / size
    
    variance = (stat[3] / iterations) - (avg_lat_iter**2)
    std = np.sqrt(max(0, variance))
    std_per_element = std / size
    
    return (gb_s, t_end - t_start, avg_lat_ns, min_ns, max_ns, 
            avg_lat_iter, min_lat_iter, max_lat_iter, 
            std_per_element, all_latencies_raw)



# -------------------------------------------------------------------
# 3. RANDOM read (random access + latency)
# -------------------------------------------------------------------
def random_access_test(size_bytes, iterations, batch ):
    """
    Measures random read access operations and average latency.
    
    IMPORTANT: Measures ONLY the memory access time, NOT the index generation.
    
    Args:
        size_bytes: Array size in bytes
        iterations: Number of repetitions
        batch: Number of random accesses per batch
    
    Returns:
        (ops_s, duration, avg_lat_ns, min_ns, max_ns, 
         avg_lat_batch, min_lat_batch, max_lat_batch,
         std_per_element, all_latencies)
    """
    np.random.seed(0)
    size = size_bytes // 8
    arr = np.ones(size, dtype=np.uint64)

    # PRE-GENERATE all indices BEFORE timing
    print("Pre-generating indices...")
    all_indices = []
    for _ in range(iterations):
        idx = np.random.randint(0, size, batch)
        all_indices.append(idx)
    print("OK")
    
    all_latencies_raw = []


    # PURE memory access timing (without index generation)
    t_start = time.perf_counter()
    for idx in all_indices:
        t0 = time.perf_counter_ns()
        _ = arr[idx].sum()
        t1 = time.perf_counter_ns()
        all_latencies_raw.append(t1 - t0)
    t_end = time.perf_counter()


    # ========================================================================
    # Statistic calculations
    # ========================================================================
    
    stat = np.zeros(4, dtype=np.float64)
    stat[0] = np.inf
    stat[1] = -np.inf
    
    overhead = timeperf 
    
    for lat_raw in all_latencies_raw:
        lat = lat_raw - overhead
        stat[0] = min(stat[0], lat)
        stat[1] = max(stat[1], lat)
        stat[2] += lat
        stat[3] += lat**2

    # ========================================================================
    # Final calculations
    # ========================================================================
    
    # Opérations per second (IOPS)
    total_ops = batch * iterations
    ops_s = total_ops / (t_end - t_start)
    
    # Latency per batch (time for processing 'batch' random access )
    avg_lat_batch = stat[2] / iterations
    min_lat_batch = stat[0]
    max_lat_batch = stat[1]

        
    # Latency per element (average time for one random access)
    avg_lat_ns = avg_lat_batch / batch
    min_ns = min_lat_batch / batch
    max_ns = max_lat_batch / batch

    # Standard deviation per batch
    variance = (stat[3] / iterations) - (avg_lat_batch**2)
    std_batch = np.sqrt(max(0, variance))


    # NOTE : Dividing by 'batch' to get std_per_element is an approximation.
    # Random accesses are NOT independent due to cache effects.
    std_per_element = std_batch / batch


    return (ops_s, t_end - t_start, avg_lat_ns, min_ns, max_ns,
            avg_lat_batch, min_lat_batch, max_lat_batch,
            std_per_element, all_latencies_raw)

# -------------------------------------------------------------------
# 4. RANDOM WRITE (Aggressive Random Writes)
# -------------------------------------------------------------------
def random_write_test(size_bytes, iterations, batch):
    """
    Measures random write access operations and average latency.
    
    IMPORTANT: Measures ONLY the memory write time, NOT the index/value generation.
    
    Args:
        size_bytes: Array size in bytes
        iterations: Number of repetitions
        batch: Number of random writes per batch
    
    Returns:
        (ops_s, duration, avg_lat_ns, min_ns, max_ns,
         avg_lat_batch, min_lat_batch, max_lat_batch,
         std_per_element, all_latencies)
    """
    np.random.seed(0)
    size = size_bytes // 8
    arr = np.ones(size, dtype=np.uint64)

    # ========================================================================
    # PRE-GENERATE all indices BEFORE timing
    # ========================================================================
    print(f"[INFO] Pre-generation of {iterations} batchs (indices + valeurs)...")
    all_indices = []
    all_values = []
    for _ in range(iterations):
        idx = np.random.randint(0, size, batch)
        vals = np.random.rand(batch) * 100  # float values between 0 and 100
        all_indices.append(idx)
        all_values.append(vals)
    print("[OK]")

    all_latencies_raw = []
    
    # PURE memory access timing (without index generation)
    t_start = time.perf_counter()
    for idx, vals in zip(all_indices, all_values):
        t0 = time.perf_counter_ns()
        arr[idx] = vals
        t1 = time.perf_counter_ns()
        all_latencies_raw.append(t1 - t0)
    t_end = time.perf_counter()


    # ========================================================================
    # Statistics calculations
    # ========================================================================
    
    stat = np.zeros(4, dtype=np.float64)
    stat[0] = np.inf
    stat[1] = -np.inf
    
    overhead = timeperf 
    
    for lat_raw in all_latencies_raw:
        lat = lat_raw - overhead
        stat[0] = min(stat[0], lat)
        stat[1] = max(stat[1], lat)
        stat[2] += lat
        stat[3] += lat**2


    # ========================================================================
    # Final calculations
    # ========================================================================
    
    # Opérations per second (IOPS)
    total_ops = batch * iterations
    ops_s = total_ops / (t_end - t_start)
    
    # Latency per batch
    avg_lat_batch = stat[2] / iterations
    min_lat_batch = stat[0]
    max_lat_batch = stat[1]


    # Latency per element
    avg_lat_ns = avg_lat_batch / batch
    min_ns = min_lat_batch / batch
    max_ns = max_lat_batch / batch

    
    # Écart-type
    variance = (stat[3] / iterations) - (avg_lat_batch**2)
    std_batch = np.sqrt(max(0, variance))
    std_per_element = std_batch / batch


    return (ops_s, t_end - t_start, avg_lat_ns, min_ns, max_ns,
            avg_lat_batch, min_lat_batch, max_lat_batch,
            std_per_element, all_latencies_raw)





# ============================================================================
# TESTS
# ============================================================================

if __name__ == "__main__":

    try:
        affinity = os.sched_getaffinity(0)
        print(f"[INFO] Process pinned to Cores: {affinity}")
    except AttributeError:
        # Particular case for Windows or systems not supporting sched_setaffinity
        print("[WARNING] sched_setaffinity not available on this system.")


    # GLOBAL SEED MANAGEMENT (Global for all functions)
    np.random.seed(0)

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode",
                        choices=["sequential_read", "sequential_write", "random_read", "random_write", "sequentiail_read_with_stride"],  # , "stride"
                        default="sequential_read")
    parser.add_argument("--size-bytes", type=int, default=1024*1024*1024) # 1 Go by default
    parser.add_argument("--iters", type=int, default=10000)
    parser.add_argument("--procs", type=int, default=1)
    parser.add_argument("--batch", type=int, default=50000)
    parser.add_argument("--stride-kb", type=int, default=64)
    args = parser.parse_args()


    if args.mode == "sequential_read":
        res = sequential_read(args.size_bytes, args.iters)
        bw, avg_elem, min_elem, max_elem = res[0], res[2], res[3], res[4]
        print(f"Seq Read {args.size_bytes} Bytes | BW: {bw:.2f} GB/s | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f})")

    elif args.mode == "sequential_write":
        res = sequential_write(args.size_bytes, args.iters)
        bw, avg_elem, min_elem, max_elem = res[0], res[2], res[3], res[4]
        print(f"Seq Write {args.size_bytes} Bytes | BW: {bw:.2f} GB/s | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f})")
        
    elif args.mode == "random_read":
        res = random_access_test(args.size_bytes, args.iters, args.batch)
        ops_s, avg_elem, min_elem, max_elem = res[0], res[2], res[3], res[4]
        print(f"Rand Read {args.size_bytes} Bytes | IOPS: {ops_s:.0f} | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f})")

    elif args.mode == "random_write":
        res = random_write_test(args.size_bytes, args.iters, args.batch)
        ops_s, avg_elem, min_elem, max_elem = res[0], res[2], res[3], res[4]
        print(f"Rand Write {args.size_bytes} Bytes | IOPS: {ops_s:.0f} | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f})")
    
