# Process Orchestration + Performance Monitoring (OS Advanced)

## Idea
We spawn multiple independent training workers (one process per config) using OS-level process creation (subprocess -> fork/exec).
The orchestrator monitors each child process (CPU%, RAM RSS peak) while running, and compares parallel vs sequential execution.

## Files
- main.py: Orchestrator (spawns workers, monitors, aggregates results, saves report)
- worker.py: Worker process (does training and prints JSON result)
- monitor.py: Process monitoring (CPU% and RAM RSS peak via psutil)
- results_parallel.json: all worker outputs + OS metrics (parallel)
- results_sequential.json: all worker outputs + OS metrics (sequential)
- report.txt: quick summary (speedup + metrics)

## Setup (Kali / Ubuntu)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
