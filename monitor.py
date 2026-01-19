# monitor.py
import time
import psutil


def monitor_processes(pid_list, sample_interval=0.2):
    """
    Monitors list of PIDs until they all exit.
    Returns dict: pid -> metrics (avg cpu, peak cpu, peak rss, etc.)
    """
    procs = {}
    metrics = {}

    # Create psutil processes
    for pid in pid_list:
        try:
            p = psutil.Process(pid)
            procs[pid] = p
            metrics[pid] = {
                "samples": 0,
                "cpu_sum": 0.0,
                "cpu_peak": 0.0,
                "rss_peak_mb": 0.0,
                "start_ts": time.time(),
                "end_ts": None,
                "alive": True,
            }
            # Prime cpu_percent to avoid first-call 0.0 artifact
            p.cpu_percent(interval=None)
        except Exception:
            # If PID is gone immediately
            metrics[pid] = {
                "samples": 0,
                "cpu_sum": 0.0,
                "cpu_peak": 0.0,
                "rss_peak_mb": 0.0,
                "start_ts": time.time(),
                "end_ts": time.time(),
                "alive": False,
                "error": "Process not accessible",
            }

    # Loop until all finish
    while True:
        alive_any = False

        for pid, p in list(procs.items()):
            if not p.is_running():
                # finished
                if metrics[pid]["alive"]:
                    metrics[pid]["alive"] = False
                    metrics[pid]["end_ts"] = time.time()
                continue

            alive_any = True
            try:
                cpu = p.cpu_percent(interval=None)  # since last call
                rss_mb = p.memory_info().rss / (1024 * 1024)

                m = metrics[pid]
                m["samples"] += 1
                m["cpu_sum"] += cpu
                if cpu > m["cpu_peak"]:
                    m["cpu_peak"] = cpu
                if rss_mb > m["rss_peak_mb"]:
                    m["rss_peak_mb"] = rss_mb
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                metrics[pid]["alive"] = False
                metrics[pid]["end_ts"] = time.time()

        if not alive_any:
            break

        time.sleep(sample_interval)

    # finalize avg cpu and durations
    for pid, m in metrics.items():
        if m.get("end_ts") is None:
            m["end_ts"] = time.time()
        duration = m["end_ts"] - m["start_ts"]
        m["duration_sec_monitored"] = round(duration, 6)
        if m["samples"] > 0:
            m["cpu_avg"] = round(m["cpu_sum"] / m["samples"], 4)
        else:
            m["cpu_avg"] = 0.0
        m["cpu_peak"] = round(m["cpu_peak"], 4)
        m["rss_peak_mb"] = round(m["rss_peak_mb"], 4)
        del m["cpu_sum"]

    return metrics
