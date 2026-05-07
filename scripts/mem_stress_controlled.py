#!/usr/bin/env python3
import numpy as np
import time
import os
import argparse
import gc

# ============================================================================
# CALIBRATION
# ============================================================================
N_calibration = 50_000

total_overhead = 0
for i in range(N_calibration):
    Tstart = time.perf_counter_ns()
    Tend = time.perf_counter_ns()
    total_overhead += (Tend - Tstart)

timeperf = total_overhead / N_calibration  

total_sum_overhead = 0
a = np.array([], dtype=np.uint64) 
result = np.zeros((), dtype=np.uint64)

for i in range(N_calibration):
    t_init = time.perf_counter_ns()
    a.sum(out=result)
    t_final = time.perf_counter_ns()
    total_sum_overhead += (t_final - t_init)

time_sum = total_sum_overhead / N_calibration  

# ============================================================================
# SEQUENTIAL READ
# ============================================================================
def sequential_read(size_bytes, iterations, duration=0):
    size = size_bytes // 8  
    src = np.ones(size, dtype=np.uint64)  
    result = np.zeros((), dtype=np.uint64)
    
    WARMUP = 50
    for _ in range(WARMUP):
        src.sum(out=result)

    all_latencies_raw = []  
    actual_iters = 0
    end_time = time.time() + duration if duration > 0 else 0

    gc.disable()
    gc.collect()
    
    t_start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        src.sum(out=result)
        t1 = time.perf_counter_ns()
        all_latencies_raw.append(t1 - t0)  
        actual_iters += 1
        
        # Proper time interruption
        if duration > 0 and time.time() > end_time:
            break
            
    t_end = time.perf_counter()
    gc.enable()
    
    stat = np.zeros(4, dtype=np.float64)  
    stat[0] = np.inf  
    stat[1] = -np.inf  
    
    overhead = (timeperf + time_sum) 
    for lat_raw in all_latencies_raw:
        lat = max(0.0, lat_raw - overhead)
        stat[0] = min(stat[0], lat)
        stat[1] = max(stat[1], lat)
        stat[2] += lat
        stat[3] += lat**2
    
    # Calculations based on actual completed iterations (actual_iters)
    bytes_processed = size_bytes * actual_iters
    gb_s = bytes_processed / (t_end - t_start) / (1024**3) if actual_iters > 0 else 0
    
    avg_lat_iter = stat[2] / actual_iters if actual_iters > 0 else 0
    min_lat_iter = stat[0]
    max_lat_iter = stat[1]
    
    avg_lat_ns = avg_lat_iter / size
    min_ns = min_lat_iter / size
    max_ns = max_lat_iter / size
    
    variance = (stat[3] / actual_iters) - (avg_lat_iter**2) if actual_iters > 0 else 0
    std = np.sqrt(max(0, variance))
    std_per_element = std / size
    
    return (gb_s, t_end - t_start, avg_lat_ns, min_ns, max_ns, 
            avg_lat_iter, min_lat_iter, max_lat_iter, 
            std_per_element, all_latencies_raw)

# ============================================================================
# SEQUENTIAL WRITE
# ============================================================================
def sequential_write(size_bytes, iterations, duration=0):
    size = size_bytes // 8
    arr = np.zeros(size, dtype=np.uint64)  
    
    all_latencies_raw = []
    WARMUP = 50
    for _ in range(WARMUP):
        arr[:] = 1
    
    actual_iters = 0
    end_time = time.time() + duration if duration > 0 else 0

    gc.disable()
    gc.collect()
    t_start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        arr[:] = 1  
        t1 = time.perf_counter_ns()
        all_latencies_raw.append(t1 - t0)
        actual_iters += 1
        
        if duration > 0 and time.time() > end_time:
            break
            
    t_end = time.perf_counter()
    gc.enable()
    
    stat = np.zeros(4, dtype=np.float64)
    stat[0] = np.inf
    stat[1] = -np.inf
    overhead = timeperf 
    
    for lat_raw in all_latencies_raw:
        lat = max(0.0, lat_raw - overhead)
        stat[0] = min(stat[0], lat)
        stat[1] = max(stat[1], lat)
        stat[2] += lat
        stat[3] += lat**2
    
    bytes_processed = size_bytes * actual_iters
    gb_s = bytes_processed / (t_end - t_start) / (1024**3) if actual_iters > 0 else 0
    
    avg_lat_iter = stat[2] / actual_iters if actual_iters > 0 else 0
    min_lat_iter = stat[0]
    max_lat_iter = stat[1]
    
    avg_lat_ns = avg_lat_iter / size
    min_ns = min_lat_iter / size
    max_ns = max_lat_iter / size
    
    variance = (stat[3] / actual_iters) - (avg_lat_iter**2) if actual_iters > 0 else 0
    std = np.sqrt(max(0, variance))
    std_per_element = std / size
    
    return (gb_s, t_end - t_start, avg_lat_ns, min_ns, max_ns, 
            avg_lat_iter, min_lat_iter, max_lat_iter, 
            std_per_element, all_latencies_raw)

# ============================================================================
# RANDOM READ
# ============================================================================
def random_access_test(size_bytes, iterations, batch, duration=0):
    np.random.seed(0)
    size = size_bytes // 8
    arr = np.ones(size, dtype=np.uint64)

    # CORRECTION : Limiter la pré-génération à 2000 itérations (Pool sécurisé)
    max_pregen = min(iterations, 2000)
    all_indices = []
    for _ in range(max_pregen):
        idx = np.random.randint(0, size, batch)
        all_indices.append(idx)
    
    all_latencies_raw = []
    actual_iters = 0
    end_time = time.time() + duration if duration > 0 else 0

    gc.disable()
    gc.collect()
    t_start = time.perf_counter()
    
    pool_idx = 0
    for _ in range(iterations):
        # On recycle les index pré-générés pour ne pas saturer la RAM
        idx = all_indices[pool_idx]
        pool_idx = (pool_idx + 1) % max_pregen

        t0 = time.perf_counter_ns()
        _ = arr[idx].sum()
        t1 = time.perf_counter_ns()
        
        all_latencies_raw.append(t1 - t0)
        actual_iters += 1
        
        if duration > 0 and time.time() > end_time:
            break
            
    t_end = time.perf_counter()
    gc.enable() 

    stat = np.zeros(4, dtype=np.float64)
    stat[0] = np.inf
    stat[1] = -np.inf
    overhead = timeperf 
    
    for lat_raw in all_latencies_raw:
        lat = max(0.0, lat_raw - overhead)
        stat[0] = min(stat[0], lat)
        stat[1] = max(stat[1], lat)
        stat[2] += lat
        stat[3] += lat**2

    total_ops = batch * actual_iters
    ops_s = total_ops / (t_end - t_start) if actual_iters > 0 else 0
    
    avg_lat_batch = stat[2] / actual_iters if actual_iters > 0 else 0
    min_lat_batch = stat[0]
    max_lat_batch = stat[1]
        
    avg_lat_ns = avg_lat_batch / batch
    min_ns = min_lat_batch / batch
    max_ns = max_lat_batch / batch

    variance = (stat[3] / actual_iters) - (avg_lat_batch**2) if actual_iters > 0 else 0
    std_batch = np.sqrt(max(0, variance))
    std_per_element = std_batch / batch

    return (ops_s, t_end - t_start, avg_lat_ns, min_ns, max_ns,
            avg_lat_batch, min_lat_batch, max_lat_batch,
            std_per_element, all_latencies_raw)

# ============================================================================
# RANDOM WRITE
# ============================================================================
def random_write_test(size_bytes, iterations, batch, duration=0):
    np.random.seed(0)
    size = size_bytes // 8
    arr = np.ones(size, dtype=np.uint64)

    # CORRECTION : Limiter la pré-génération à 2000 itérations
    max_pregen = min(iterations, 2000)
    all_indices = []
    all_values = []
    for _ in range(max_pregen):
        idx = np.random.randint(0, size, batch)
        vals = np.random.rand(batch) * 100  
        all_indices.append(idx)
        all_values.append(vals)

    all_latencies_raw = []
    actual_iters = 0
    end_time = time.time() + duration if duration > 0 else 0
    
    gc.disable()
    gc.collect()
    t_start = time.perf_counter()
    
    pool_idx = 0
    for _ in range(iterations):
        idx = all_indices[pool_idx]
        vals = all_values[pool_idx]
        pool_idx = (pool_idx + 1) % max_pregen

        t0 = time.perf_counter_ns()
        arr[idx] = vals
        t1 = time.perf_counter_ns()
        
        all_latencies_raw.append(t1 - t0)
        actual_iters += 1
        
        if duration > 0 and time.time() > end_time:
            break
            
    t_end = time.perf_counter()
    gc.enable()

    stat = np.zeros(4, dtype=np.float64)
    stat[0] = np.inf
    stat[1] = -np.inf
    overhead = timeperf 
    
    for lat_raw in all_latencies_raw:
        lat = max(0.0, lat_raw - overhead)
        stat[0] = min(stat[0], lat)
        stat[1] = max(stat[1], lat)
        stat[2] += lat
        stat[3] += lat**2

    total_ops = batch * actual_iters
    ops_s = total_ops / (t_end - t_start) if actual_iters > 0 else 0
    
    avg_lat_batch = stat[2] / actual_iters if actual_iters > 0 else 0
    min_lat_batch = stat[0]
    max_lat_batch = stat[1]

    avg_lat_ns = avg_lat_batch / batch
    min_ns = min_lat_batch / batch
    max_ns = max_lat_batch / batch
    
    variance = (stat[3] / actual_iters) - (avg_lat_batch**2) if actual_iters > 0 else 0
    std_batch = np.sqrt(max(0, variance))
    std_per_element = std_batch / batch

    return (ops_s, t_end - t_start, avg_lat_ns, min_ns, max_ns,
            avg_lat_batch, min_lat_batch, max_lat_batch,
            std_per_element, all_latencies_raw)

# ===========================================================================
# MAIN EXECUTION
# ===========================================================================
if __name__ == "__main__":
    try:
        affinity = os.sched_getaffinity(0)
    except AttributeError:
        pass

    np.random.seed(0)

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["sequential_read", "sequential_write", "random_read", "random_write", "sequential_read_with_stride"], default="sequential_read")
    parser.add_argument("--size-bytes", type=int, default=1024*1024*1024) 
    parser.add_argument("--iters", type=int, default=10000)
    parser.add_argument("--procs", type=int, default=1)
    parser.add_argument("--batch", type=int, default=50000)
    parser.add_argument("--duration", type=int, default=0)
    parser.add_argument("--target-mb", type=int, default=0)
    parser.add_argument("--stride-kb", type=int, default=64)
    args = parser.parse_args()
    
    # ---------------- DYNAMIC ITERATIONS ----------------
    dynamic_iters = args.iters
    
    if args.target_mb > 0:
        # VOLUME MODE (Work-Bound)
        if "random" in args.mode:
            # For random, we calculate based on batch size
            dynamic_iters = max(1, int((args.target_mb * 1024 * 1024) / (args.batch * 8)))
        else:
            # For sequential, we calculate based on the full array size
            dynamic_iters = max(1, int((args.target_mb * 1024 * 1024) / args.size_bytes))
            
    elif args.duration > 0:
        # CONSTANT TIME MODE (Time-Bound)
        # We give an infinite number of iterations, the internal timer will stop the loop!
        dynamic_iters = 999999999 

    # ---------------- EXECUTION ----------------
    if args.mode == "sequential_read":
        res = sequential_read(args.size_bytes, dynamic_iters, args.duration)
        bw, avg_elem, min_elem, max_elem, std = res[0], res[2], res[3], res[4], res[8]
        print(f"Seq Read {args.size_bytes} Bytes | BW: {bw:.2f} GB/s | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f}, Std: {std:.2f})")
        
    elif args.mode == "sequential_write":
        res = sequential_write(args.size_bytes, dynamic_iters, args.duration)
        bw, avg_elem, min_elem, max_elem, std = res[0], res[2], res[3], res[4], res[8]
        print(f"Seq Write {args.size_bytes} Bytes | BW: {bw:.2f} GB/s | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f}, Std: {std:.2f})")
        
    elif args.mode == "random_read":
        res = random_access_test(args.size_bytes, dynamic_iters, args.batch, args.duration)
        ops_s, avg_elem, min_elem, max_elem, std = res[0], res[2], res[3], res[4], res[8]
        print(f"Rand Read {args.size_bytes} Bytes | IOPS: {ops_s:.0f} | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f}, Std: {std:.2f})")

    elif args.mode == "random_write":
        res = random_write_test(args.size_bytes, dynamic_iters, args.batch, args.duration)
        ops_s, avg_elem, min_elem, max_elem, std = res[0], res[2], res[3], res[4], res[8]
        print(f"Rand Write {args.size_bytes} Bytes | IOPS: {ops_s:.0f} | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f}, Std: {std:.2f})")