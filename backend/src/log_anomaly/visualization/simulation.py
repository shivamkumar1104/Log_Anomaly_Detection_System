# backend/src/log_anomaly/visualization/simulation.py
from __future__ import annotations

import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

HOSTS = [f"host-{i}" for i in range(1, 6)]
SERVICES = ["web", "db", "cache", "api"]
TEMPLATES = [
    "User {user} logged in",
    "Failed query on table {table}",
    "Cache miss for key {key}",
    "Request timeout after {ms}ms",
]

def _random_template():
    tmpl = random.choice(TEMPLATES)
    # Very lightweight token substitution – just to give some variety
    return tmpl.format(
        user=random.randint(1000, 9999),
        table=random.choice(["orders", "customers", "items"]),
        key=random.randint(1, 100),
        ms=random.randint(100, 5000),
    )

def generate_synthetic(
    size: int = 500,
    prevalence: float = 0.05,
    seed: int | None = None,
) -> pd.DataFrame:
    """Return a DataFrame that mimics the output of the real pipeline."""
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    now = datetime.utcnow()
    timestamps = [
        now - timedelta(minutes=random.randint(0, 1440)) for _ in range(size)
    ]
    messages = [_random_template() for _ in range(size)]
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "host": np.random.choice(HOSTS, size),
            "service": np.random.choice(SERVICES, size),
            "message": messages,
            "template": messages,
        }
    )
    # Ground‑truth flag
    df["ground_truth"] = np.random.rand(size) < prevalence
    return df
