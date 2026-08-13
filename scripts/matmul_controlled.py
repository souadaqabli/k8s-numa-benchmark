#!/usr/bin/env python3
"""
Matmul workload, mirroring the interface of mem_stress_controlled.py so it
stays 100% compatible with script_controlled.py (perf wrapping, parsing,
work-bound/time-bound modes) with zero modification to the existing
measurement pipeline.

Interface identical to mem_stress_controlled.py:
  --mode        : a single useful mode here ("matmul"), kept for CLI compatibility
  --size-bytes  : target size of ONE N x N matrix in bytes (determines N)
  --target-mb   : work-bound mode, total volume of data "processed" (same
                  spirit as your memory-stress work-bound mode at 10240 MB)
  --duration    : time-bound mode
  --iters       : standard mode (fixed number of iterations)

Output: same line format as mem_stress_controlled.py, so the existing regex
parsing in script_controlled.py (BW:/Lat:/Min:/Max:/Std:) works unchanged.
"""
import numpy as np
import time
import os
import argparse
import gc

# Prevent BLAS from parallelizing across multiple threads: CRITICAL to keep
# methodology consistent with numactl --physcpubind.
# Without this, a pod pinned to 1 core could still trigger work on other
# cores via OpenBLAS/MKL's internal threading, invalidating the
# Baseline/Extreme/Extreme-Cross comparison.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"


def matmul_work(size_bytes, iterations, duration=0, op="gemm"):
    """Repeatedly multiplies matrices, where N is chosen so that one N x N
    matrix weighs approximately `size_bytes` in memory.

    op="gemm" : A @ B (matrix-matrix, BLAS Level 3, high arithmetic intensity,
                cache-blocking friendly -> the original, compute-bound workload)
    op="gemv" : A @ v (matrix-vector, BLAS Level 2, arithmetic intensity ~1,
                inherently memory-bound -> the new comparison point, closer
                to the memory-stress profile)

    One "iteration" = one full multiplication (computation + result write).
    """

    n = max(8, int(np.sqrt(size_bytes / 8)))

    rng = np.random.default_rng(0)
    A = rng.random((n, n))
    if op == "gemv":
        B = rng.random(n)          # vector
    else:
        B = rng.random((n, n))

    WARMUP = 3
    for _ in range(WARMUP):
        C = A @ B 

    all_latencies_raw = []
    actual_iters = 0
    end_time = time.time() + duration if duration > 0 else 0

    gc.disable()
    gc.collect()

    t_start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        C = A @ B
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
    for lat in all_latencies_raw:
        stat[0] = min(stat[0], lat)
        stat[1] = max(stat[1], lat)
        stat[2] += lat
        stat[3] += lat ** 2

    avg_lat_iter = stat[2] / actual_iters if actual_iters > 0 else 0
    min_lat_iter = stat[0] if actual_iters > 0 else 0
    max_lat_iter = stat[1] if actual_iters > 0 else 0
    variance = (stat[3] / actual_iters) - (avg_lat_iter ** 2) if actual_iters > 0 else 0
    std_ns = np.sqrt(max(0, variance))

    # "bytes processed" per iteration : differs between GEMM and GEMV since
    # the second operand's size differs (matrix vs vector)
    if op == "gemv":
        # read A (n*n) + read v (n) + write result (n)
        bytes_per_iter = (n * n * 8) + (n * 8) + (n * 8)
    else:
        # read A + read B + write C (all n*n)
        bytes_per_iter = 3 * (n * n * 8)
    bytes_processed = bytes_per_iter * actual_iters
    gb_s = bytes_processed / (t_end - t_start) / (1024 ** 3) if actual_iters > 0 else 0

    return gb_s, (t_end - t_start), avg_lat_iter, min_lat_iter, max_lat_iter, std_ns, n, actual_iters, bytes_per_iter


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["matmul"], default="matmul")
    parser.add_argument("--op", choices=["gemm", "gemv"], default="gemm",
                         help="gemm = A@B (compute-bound, BLAS Level 3, original workload); "
                              "gemv = A@v (memory-bound, BLAS Level 2, new comparison point)")
    parser.add_argument("--size-bytes", type=int, default=64 * 1024 * 1024)  # 64MB per matrix by default
    parser.add_argument("--iters", type=int, default=50)
    parser.add_argument("--batch", type=int, default=0)  
    parser.add_argument("--duration", type=int, default=0)
    parser.add_argument("--target-mb", type=int, default=0)
    args = parser.parse_args()

    n_estimate = max(8, int(np.sqrt(args.size_bytes / 8)))
    if args.op == "gemv":
        bytes_per_iter_estimate = (n_estimate * n_estimate * 8) + (n_estimate * 8) + (n_estimate * 8)
    else:
        bytes_per_iter_estimate = 3 * (n_estimate * n_estimate * 8)

    dynamic_iters = args.iters
    if args.target_mb > 0:
        target_bytes = args.target_mb * 1024 * 1024
        dynamic_iters = max(1, int(target_bytes / bytes_per_iter_estimate))
    elif args.duration > 0:
        dynamic_iters = 999999999

    gb_s, elapsed, avg_ns, min_ns, max_ns, std_ns, n, actual_iters, bytes_per_iter = matmul_work(
        args.size_bytes, dynamic_iters, args.duration, op=args.op
    )

    # Output format IDENTICAL to mem_stress_controlled.py so the existing
    # regex parsing in script_controlled.py (run_perf) works unmodified.
    op_label = "Matmul" if args.op == "gemm" else "Matvec"
    print(f"{op_label} N={n} {args.size_bytes} Bytes | BW: {gb_s:.2f} GB/s | "
          f"Lat: {avg_ns:.2f} ns (Min: {min_ns:.2f}, Max: {max_ns:.2f}, Std: {std_ns:.2f})")