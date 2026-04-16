# Datasets/top_processes

## ⚠️ Privacy Notice

**IMPORTANT:** This repository contains system performance analysis tools. When running on actual system data:

- Raw process data files (e.g., `raw_top_processes.out`) contain **sensitive information** including usernames, process names, and system details
- **Do NOT commit** raw data files, parquet files, or generated reports to public repositories
- Use the provided `.gitignore` to prevent accidental commits of sensitive data
- For public sharing, use **anonymized data only**

See [Anonymization](#anonymization) section below for guidance.

---

## CPU Time Series Visualization

__Plot Features:__

- Mean CPU % (blue line) - Average CPU usage across all processes per snapshot
- Median CPU % (orange line) - Median CPU usage per snapshot
- Max CPU % (red line) - Peak CPU usage per snapshot
- Shaded area - Mean ± 1 standard deviation band showing CPU variability

__Key Statistics:__

- Time span: 05:13:22 - 05:52:54 (~40 minutes)
- Mean CPU: 0.20% (average across all snapshots)
- Median CPU: 0.00% (most processes idle)
- Peak CPU: 220.20% (multi-core utilization, exceeds 100% due to multi-threaded processes)
- Data points: 1,120 time snapshots

__Key Observations:__

**The plot shows several CPU usage spikes around:**

- 05:22:00 area (first major spike, ~190% max)
- 05:37:00 area (second major spike, ~220% max)
- 05:47:00 area (third major spike, ~170% max)

These spikes represent periods of high computational activity, while much of the time shows minimal CPU usage (close to 0%), indicating the system is mostly idle.

__Output File:__

- Location: cpu-pct.png
- Size: 126 KB
- Dimensions: 1389 × 590 pixels
- Resolution: 100 DPI

__Usage:__

```bash
.venv/bin/python3 plot_cpu_timeseries.py formatted_data/top_processes.parquet -o cpu-pct.png
```

---

## Anonymization

To prepare data for public sharing, anonymize usernames and sensitive process names:

```python
import pandas as pd
import hashlib

def anonymize_data(df):
    """Anonymize sensitive user and process information."""
    df = df.copy()
    
    # Map usernames to generic identifiers
    users = df['USER'].unique()
    user_map = {user: f'user_{i}' for i, user in enumerate(users)}
    df['USER'] = df['USER'].map(user_map)
    
    # Optionally hash process names
    df['COMMAND_HASH'] = df['COMMAND'].apply(
        lambda x: hashlib.md5(x.encode()).hexdigest()[:8]
    )
    
    return df

# Usage:
df = pd.read_parquet('formatted_data/top_processes.parquet')
df_anon = anonymize_data(df)
df_anon.to_parquet('formatted_data/top_processes_anonymized.parquet', index=False)
```

**Note:** The `.gitignore` file is configured to prevent accidental commits of parquet files.
