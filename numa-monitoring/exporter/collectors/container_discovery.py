import subprocess
import json

def get_active_pods():
    active_pods = {}
    try:
        print("[Discovery] --- SCAN START ---", flush=True)
        
        # 1. Use ABSOLUTE path for k3s (crucial for systemd)
        cmd_ps = ["sudo", "/usr/local/bin/k3s", "crictl", "ps", "-q"]
        result_ps = subprocess.run(cmd_ps, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        out_ps = result_ps.stdout.decode('utf-8').strip()
        err_ps = result_ps.stderr.decode('utf-8').strip()
        
        if err_ps:
            print(f"[Discovery] ERROR k3s ps: {err_ps}", flush=True)
            
        container_ids = out_ps.split('\n')
        print(f"[Discovery] Containers found: {len([c for c in container_ids if c])}", flush=True)
        
        for cid in container_ids:
            if not cid:
                continue
                
            # 2. Inspect each container
            cmd_inspect = ["sudo", "/usr/local/bin/k3s", "crictl", "inspect", cid]
            result_inspect = subprocess.run(cmd_inspect, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            inspect_output = result_inspect.stdout.decode('utf-8')
            
            if not inspect_output:
                continue
                
            data = json.loads(inspect_output)
            labels = data.get('status', {}).get('labels', {})
            pod_name = labels.get('io.kubernetes.pod.name', 'unknown')
            
            # Strict filter
            if "job" not in pod_name and "gem" not in pod_name and "bench" not in pod_name:
                continue
                
            root_pid = str(data.get('info', {}).get('pid', ''))
            print(f"[Discovery] Analyzing pod: {pod_name} | Root PID: {root_pid}", flush=True)
            
            if not root_pid:
                continue
                
            # 3. Exact Bash logic to find the worker process
            target_pid = root_pid 
            try:
               # bash_cmd = f"PERF_PID=$(pgrep -P {root_pid} -f perf | head -1); [ -n \"$PERF_PID\" ] && pgrep -P $PERF_PID python3 | head -1"
                bash_cmd = f"PIDS=\"{root_pid}\"; CHILDS=$(pgrep -d, -P {root_pid}); [ -n \"$CHILDS\" ] && PIDS=\"$PIDS,$CHILDS\"; PERF_PID=$(pgrep -P $PIDS -f perf | head -1); [ -n \"$PERF_PID\" ] && pgrep -P $PERF_PID python3 | head -1"
                res = subprocess.run(bash_cmd, shell=True, stdout=subprocess.PIPE)
                child_pid = res.stdout.decode('utf-8').strip()
                
                if child_pid and child_pid.isdigit():
                    target_pid = child_pid
                    print(f"[Discovery] -> BINGO! True worker PID: {target_pid}", flush=True)
                else:
                    print(f"[Discovery] -> Bash FAILED. Fallback to Root PID: {root_pid}", flush=True)
                    
            except Exception as e:
                print(f"[Discovery] Error executing Bash: {e}", flush=True)
                
            active_pods[target_pid] = pod_name
            
        print(f"[Discovery] --- SCAN COMPLETE. Result: {active_pods} ---", flush=True)
        
    except Exception as e:
        print(f"[Discovery] TOTAL CRASH: {e}", flush=True)
        
    return active_pods
