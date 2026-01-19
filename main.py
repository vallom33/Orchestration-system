# main.py
import json
import os
import subprocess
import time
from threading import Thread

from monitor import monitor_processes


CONFIGS = [
    {"seed": 1, "lr": 0.01,  "epochs": 4000, "n_samples": 5000, "n_features": 30},
    {"seed": 2, "lr": 0.02,  "epochs": 4000, "n_samples": 5000, "n_features": 30},
    {"seed": 3, "lr": 0.005, "epochs": 4000, "n_samples": 5000, "n_features": 30},
    {"seed": 4, "lr": 0.01,  "epochs": 6000, "n_samples": 5000, "n_features": 30},
]


def _run_worker(cfg):
    """
    Launch worker.py as separate OS process.
    Returns (proc, cfg)
    """
    cfg_json = json.dumps(cfg)
    p = subprocess.Popen(
        ["python3", "worker.py", cfg_json],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return p


def run_parallel(sample_interval=0.2):
    procs = []
    pid_list = []

    start_total = time.time()

    # Spawn all
    for cfg in CONFIGS:
        p = _run_worker(cfg)
        procs.append((cfg, p))
        pid_list.append(p.pid)
        print(f"[PAR] Started PID={p.pid} cfg={cfg}")

    # Start monitor in parallel thread
    mon_result = {}

    def mon_task():
        nonlocal mon_result
        mon_result = monitor_processes(pid_list, sample_interval=sample_interval)

    t = Thread(target=mon_task, daemon=True)
    t.start()

    # Collect worker outputs
    results = []
    for cfg, p in procs:
        out, err = p.communicate()

        if p.returncode != 0:
            results.append({
                "pid": p.pid,
                "seed": cfg["seed"],
                "error": err.strip() or "worker failed"
            })
            continue

        try:
            r = json.loads(out.strip())
        except Exception:
            r = {
                "pid": p.pid,
                "seed": cfg["seed"],
                "error": "Invalid JSON from worker",
                "raw_out_tail": out[-300:],
                "raw_err_tail": err[-300:],
            }

        results.append(r)

    # Ensure monitor thread finished
    t.join(timeout=10)

    end_total = time.time()

    # Attach monitoring metrics to each result
    for r in results:
        pid = r.get("pid")
        if pid in mon_result:
            r["os_metrics"] = mon_result[pid]
        else:
            r["os_metrics"] = None

    results.sort(key=lambda x: x.get("seed", 0))
    total_time = round(end_total - start_total, 6)
    return results, total_time


def run_sequential(sample_interval=0.2):
    results = []
    total_start = time.time()

    for cfg in CONFIGS:
        start_one = time.time()
        p = _run_worker(cfg)
        pid = p.pid

        # Monitor single PID while it runs
        mon = {}
        def mon_task():
            nonlocal mon
            mon = monitor_processes([pid], sample_interval=sample_interval)

        t = Thread(target=mon_task, daemon=True)
        t.start()

        out, err = p.communicate()
        t.join(timeout=10)

        end_one = time.time()

        if p.returncode != 0:
            results.append({
                "pid": pid,
                "seed": cfg["seed"],
                "error": err.strip() or "worker failed"
            })
            continue

        r = json.loads(out.strip())
        r["wall_time_one_sec"] = round(end_one - start_one, 6)
        r["os_metrics"] = mon.get(pid)
        results.append(r)

    total_end = time.time()
    results.sort(key=lambda x: x.get("seed", 0))
    total_time = round(total_end - total_start, 6)
    return results, total_time


def summarize(results):
    # compute peaks across all workers
    rss_peaks = []
    cpu_avgs = []
    cpu_peaks = []
    train_times = []

    for r in results:
        if "train_time_sec" in r:
            train_times.append(r["train_time_sec"])
        m = r.get("os_metrics") or {}
        if m:
            rss_peaks.append(m.get("rss_peak_mb", 0.0))
            cpu_avgs.append(m.get("cpu_avg", 0.0))
            cpu_peaks.append(m.get("cpu_peak", 0.0))

    def safe_max(xs): return round(max(xs), 4) if xs else 0.0
    def safe_avg(xs): return round(sum(xs) / len(xs), 4) if xs else 0.0

    return {
        "workers": len(results),
        "train_time_avg_sec": round(sum(train_times) / len(train_times), 6) if train_times else 0.0,
        "rss_peak_max_mb": safe_max(rss_peaks),
        "rss_peak_avg_mb": safe_avg(rss_peaks),
        "cpu_avg_avg": safe_avg(cpu_avgs),
        "cpu_peak_max": safe_max(cpu_peaks),
    }


def write_report(par_time, seq_time, par_sum, seq_sum, filename="report.txt"):
    speedup = round(seq_time / par_time, 4) if par_time > 0 else 0.0

    lines = []
    lines.append("=== ORCHESTRATION PROJECT REPORT ===")
    lines.append(f"Host Parent PID: {os.getpid()}")
    lines.append("")
    lines.append("---- TIMING ----")
    lines.append(f"Parallel total wall time  : {par_time} sec")
    lines.append(f"Sequential total wall time: {seq_time} sec")
    lines.append(f"Speedup (seq/par)         : {speedup}x")
    lines.append("")
    lines.append("---- PARALLEL METRICS (across workers) ----")
    for k, v in par_sum.items():
        lines.append(f"{k}: {v}")
    lines.append("")
    lines.append("---- SEQUENTIAL METRICS (across workers) ----")
    for k, v in seq_sum.items():
        lines.append(f"{k}: {v}")
    lines.append("")
    lines.append("Notes:")
    lines.append("- CPU% depends on number of vCPUs assigned in VirtualBox.")
    lines.append("- Peak RSS is per process; parallel may increase total RAM usage.")
    lines.append("- Sample interval affects metric precision (default 0.2s).")

    with open(filename, "w") as f:
        f.write("\n".join(lines))


def main():
    print("=== ORCHESTRATOR (subprocess + OS monitoring) ===")
    print("Parent PID:", os.getpid())
    print("Running on:", os.uname().sysname, os.uname().release)

    sample_interval = 0.2  # adjust if needed

    par_results, par_time = run_parallel(sample_interval=sample_interval)
    with open("results_parallel.json", "w") as f:
        json.dump(par_results, f, indent=2)

    seq_results, seq_time = run_sequential(sample_interval=sample_interval)
    with open("results_sequential.json", "w") as f:
        json.dump(seq_results, f, indent=2)

    par_sum = summarize(par_results)
    seq_sum = summarize(seq_results)

    write_report(par_time, seq_time, par_sum, seq_sum, filename="report.txt")

    print("\n=== DONE ===")
    print("Saved: results_parallel.json, results_sequential.json, report.txt")


if __name__ == "__main__":
    main()
