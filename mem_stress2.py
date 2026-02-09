#!/usr/bin/env python3
# mem_stress.py -- various memory load patterns
import numpy as np
import time
import argparse
import multiprocessing as mp


#-------------------------------------------------
# 1. Sequential read  
#-------------------------------------------------
def sequential_read(size_bytes, iterations):
    """
    Benchmarks sequential memory read performance (linear access).
    """
    size = size_bytes // 8  # éléments float64 (8 bytes)
    src = np.ones(size, dtype=np.uint64)
    
    stat = np.zeros(4, dtype = np.uint64)
    stat[0] = np.iinfo(np.uint64).max
    
    t_start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        _ = src.sum()  
        t1 = time.perf_counter_ns()
        
        lat = t1 - t0
        stat[0] = min(stat[0], lat)   # le minimum sur toutes les iterations
        stat[1] = max(stat[1], lat)   # le maximum sur toutes les iterations
        stat[2] = stat[2] + lat       # temps total passe a lire le tableau
        stat[3] += lat**2

    t_end = time.perf_counter()
    
    bytes_processed = size_bytes * iterations
    gb_s = bytes_processed / (t_end - t_start) / (1024**3)

    avg_lat_iter = (stat[2] / iterations)   # latence moyenne par iteration, le temps moyen qu'il faut pour lire une fois tout le bloc mémoire
    avg_lat_ns = (stat[2] / iterations) / len(src)          # latence moyenne par element 
    
    variance = (stat[3] / iterations) - (avg_lat_iter**2)
    std = np.sqrt(max(0, variance))

    min_ns = stat[0] / len(src) # le temps pour acceder a un seul element dans la meilleure iteration
    max_ns = stat[1] / len(src)

    return gb_s, t_end - t_start , avg_lat_ns, min_ns, max_ns, avg_lat_iter, stat[0], stat[1],std


# -------------------------------------------------------------------
# 3-. SEQUENTIAL WRITE 
# -------------------------------------------------------------------
def sequential_write(size_bytes, iterations):
    """
    Benchmarks sequential memory write performance (linear fill).
    """
    size = size_bytes // 8 # float64
    arr = np.ones(size, dtype=np.uint64)
    
    stat = np.zeros(4, dtype = np.uint64)
    stat[0] = np.iinfo(np.uint64).max
    
    t_start = time.perf_counter()
    
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        arr[:] = 1 
        t1 = time.perf_counter_ns()
        
        lat = t1 - t0
        stat[0] = min(stat[0], lat)   # le minimum sur toutes les iterations
        stat[1] = max(stat[1], lat)   # le maximum sur toutes les iterations
        stat[2] = stat[2] + lat       # temps total passe a ecrire le tableau
        stat[3] += lat**2

    t_end = time.perf_counter()
    
    bytes_processed = size_bytes * iterations
    gb_s = bytes_processed / (t_end - t_start) / (1024**3)
    
    # Conversions
    avg_lat_iter = (stat[2] / iterations)   # latence moyenne par iteration, le temps moyen qu'il faut pour lire une fois tout le bloc mémoire
    avg_lat_ns = (stat[2] / iterations) / len(arr) # latence moyenne par element 

    variance = (stat[3] / iterations) - (avg_lat_iter**2)
    std = np.sqrt(max(0, variance))

    min_ns = stat[0] / len(arr) # le temps pour ecrire un seul element dans la meilleure iteration
    max_ns = stat[1] / len(arr)
    
    return gb_s, t_end - t_start, avg_lat_ns, min_ns, max_ns, avg_lat_iter, stat[0], stat[1], std


# -------------------------------------------------------------------
# 4. RANDOM read (random access + latency)
# -------------------------------------------------------------------
def random_access_test(size_bytes, iterations, batch):
    """
    Measures complex random read access operations and average latency.
    """
    np.random.seed(0)
    size = size_bytes // 8

    arr = np.ones(size, dtype=np.uint64)
    
    stat = np.zeros(4, dtype=np.uint64)
    stat[0] = np.iinfo(np.uint64).max
    

    t_start = time.perf_counter()

    for _ in range(iterations):
        idx = np.random.randint(0, size, batch)
        
        t0 = time.perf_counter_ns()
        _ = arr[idx].sum()
        t1 = time.perf_counter_ns()
        
        lat = t1 - t0 # Temps pour traiter UN BATCH
        
        stat[0] = min(stat[0], lat)   # le minimum pour un batch
        stat[1] = max(stat[1], lat)   # le maximum pour un batch
        stat[2] = stat[2] + lat       # temps total cumulé
        stat[3] += lat**2

    t_end = time.perf_counter()
        
    total_ops = batch * iterations
    ops_s = total_ops / (t_end - t_start)

    avg_lat_ns = (stat[2] / iterations) / batch # latence moyenne par element
    min_ns = stat[0] / batch # le temps pour un element dans le meilleur batch
    max_ns = stat[1] / batch

    ratio = size / batch
    # Conversions : Ici on divise par 'batch' car lat correspond à un lot de 'batch' accès
    avg_lat_iter = (stat[2] / iterations) * ratio

    variance = (stat[3] / iterations) - ((stat[2] / iterations)**2)
    std = np.sqrt(max(0, variance))
    
    return ops_s , t_end - t_start, avg_lat_ns, min_ns, max_ns, avg_lat_iter, stat[0] * ratio, stat[1] * ratio, std

# -------------------------------------------------------------------
# 5. RANDOM WRITE (Aggressive Random Writes)
# -------------------------------------------------------------------
def random_write_test(size_bytes, iterations, batch):
    """
    Measures the performance of aggressive random memory writes.
    """
    np.random.seed(0)
    size = size_bytes  // 8
    arr = np.ones(size, dtype=np.uint64)
    
    stat = np.zeros(4, dtype=np.uint64)
    stat[0] = np.iinfo(np.uint64).max
    
    ops = 0
    

    t_start = time.perf_counter()
    for _ in range(iterations):
        idx = np.random.randint(0, size, batch)
        #vals = np.random.rand(batch)
        vals = np.random.randint(0, 100, batch, dtype=np.uint64)

        t0 = time.perf_counter_ns()
        arr[idx] = vals
        t1 = time.perf_counter_ns()
        
        lat = t1 - t0
        stat[0] = min(stat[0], lat)   # le minimum pour un batch
        stat[1] = max(stat[1], lat)   # le maximum pour un batch
        stat[2] = stat[2] + lat       # temps total cumulé
        stat[3] += lat**2

    t_end = time.perf_counter()
        
    total_ops = batch * iterations
    ops_s = total_ops / (t_end - t_start)

 
    avg_lat_ns = (stat[2] / iterations) / batch # latence moyenne par element
    min_ns = stat[0] / batch # le temps pour un element dans le meilleur batch
    max_ns = stat[1] / batch

    # Conversions
    ratio = size / batch
    avg_lat_iter = (stat[2] / iterations) * ratio

    variance = (stat[3] / iterations) - ((stat[2] / iterations)**2)
    std = np.sqrt(max(0, variance))
    
    return ops_s, t_end - t_start, avg_lat_ns, min_ns, max_ns, avg_lat_iter, stat[0] * ratio, stat[1] * ratio, std
    

def stride_test(size_bytes, duration_s, stride_bytes=4096):
    # Test TLB (Saut variable)
    stride_idx = stride_bytes // 8
    if stride_idx < 1: stride_idx = 1
    
    size = size_bytes // 8
    arr = np.random.rand(size)
    
    start = time.time()
    ops = 0
    while time.time() - start < duration_s:
        # Lecture linéaire avec sauts
        _ = arr[::stride_idx].sum() 
        ops += (size // stride_idx)
    return ops / duration_s


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
if __name__ == "__main__":
    # GESTION UNIQUE DU SEED ICI (Global pour toutes les fonctions)
    np.random.seed(0)

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode",
                        choices=["sequential_read", "sequential_write", "random_read", "random_write", "stride"],
                        default="sequential_read")
    parser.add_argument("--size-bytes", type=int, default=1024*1024*1024) # 1 Go par défaut
    parser.add_argument("--iters", type=int, default=10000)
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--procs", type=int, default=1)
    parser.add_argument("--batch", type=int, default=50000)
    parser.add_argument("--stride-bytes", type=int, default=4096)
    args = parser.parse_args()

    # NOTE : Mise à jour des prints pour afficher Avg (Moyenne), Min et Max.

    #if args.mode == "copy":
        #bw, dur, avg, mini, maxi = copy_test(args.size_bytes, args.iters)
        #print(f"Copy {args.size_bytes} MiB | BW: {bw:.2f} GB/s | Lat: {avg:.2f} ns (Min: {mini:.2f}, Max: {maxi:.2f})")

    if args.mode == "sequential_read":
        res = sequential_read(args.size_bytes, args.iters)
        bw, avg_elem, min_elem, max_elem = res[0], res[2], res[3], res[4]
        print(f"Seq Read {args.size_bytes} Bytes | BW: {bw:.2f} GB/s | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f})")

    elif args.mode == "sequential_write":
        res = sequential_write(args.size_bytes, args.iters)
        bw, avg_elem, min_elem, max_elem = res[0], res[2], res[3], res[4]
        print(f"Seq Write {args.size_bytes} Bytes | BW: {bw:.2f} GB/s | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f})")
        
    elif args.mode == "random_read":
        #ops_s, avg, mini, maxi = random_access_test(args.size_bytes, args.duration, args.batch)
        #print(f"Rand Read {args.size_bytes} MiB | IOPS: {ops_s:.0f} | Lat: {avg:.2f} ns (Min: {mini:.2f}, Max: {maxi:.2f})")
        res = random_access_test(args.size_bytes, args.iters, args.batch)
        ops_s, avg_elem, min_elem, max_elem = res[0], res[2], res[3], res[4]
        print(f"Rand Read {args.size_bytes} Bytes | IOPS: {ops_s:.0f} | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f})")

    elif args.mode == "random_write":
        res = random_write_test(args.size_bytes, args.iters, args.batch)
        ops_s, avg_elem, min_elem, max_elem = res[0], res[2], res[3], res[4]
        print(f"Rand Write {args.size_bytes} Bytes | IOPS: {ops_s:.0f} | Lat: {avg_elem:.2f} ns (Min: {min_elem:.2f}, Max: {max_elem:.2f})")
    
    elif args.mode == "stride":
        ops_s = stride_test(args.size_bytes, args.duration, args.stride_bytes)
        print(f"Stride ops/s: {ops_s:.0f}")