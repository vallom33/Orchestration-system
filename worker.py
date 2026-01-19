# worker.py
import json
import os
import sys
import time
import numpy as np


def train_model(config):
    # Seed for reproducibility per process
    np.random.seed(config["seed"])

    # Synthetic dataset
    X = np.random.randn(config["n_samples"], config["n_features"])
    true_w = np.random.randn(config["n_features"])
    y_prob = 1 / (1 + np.exp(-(X @ true_w)))
    y = (y_prob > 0.5).astype(int)

    # Model params
    w = np.zeros(config["n_features"])
    lr = float(config["lr"])
    epochs = int(config["epochs"])

    start = time.time()

    # Gradient descent (logistic regression)
    for _ in range(epochs):
        preds = 1 / (1 + np.exp(-(X @ w)))
        grad = X.T @ (preds - y) / len(y)
        w -= lr * grad

    end = time.time()

    # accuracy
    final_preds = (1 / (1 + np.exp(-(X @ w))) > 0.5).astype(int)
    acc = float((final_preds == y).mean())

    return {
        "pid": os.getpid(),
        "seed": config["seed"],
        "lr": lr,
        "epochs": epochs,
        "n_samples": config["n_samples"],
        "n_features": config["n_features"],
        "train_time_sec": round(end - start, 6),
        "accuracy": round(acc, 6),
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing config JSON in argv"}))
        sys.exit(1)

    try:
        config = json.loads(sys.argv[1])
    except Exception as e:
        print(json.dumps({"error": f"Bad JSON config: {e}"}))
        sys.exit(2)

    # Optional: allow “workload factor” to make CPU usage more visible in VM
    # If provided, we can repeat training loops (NOT needed usually)
    repeats = int(config.get("repeats", 1))
    best = None
    for _ in range(repeats):
        best = train_model(config)

    print(json.dumps(best))  # One JSON line only


if __name__ == "__main__":
    main()
