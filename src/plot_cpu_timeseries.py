#!/usr/bin/env python3
"""
Generate a time series plot of CPU percentage from parsed top data.
"""

import argparse
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta


def plot_cpu_timeseries(parquet_file: str, output_file: str = "cpu-pct.png"):
    """
    Create a time series plot of CPU percentage.

    Args:
        parquet_file: Path to the parquet file with parsed top data
        output_file: Output PNG file path
    """
    parquet_path = Path(parquet_file)

    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_file}")

    print(f"Loading data from {parquet_file}...")
    df = pd.read_parquet(parquet_file)

    # Convert TIMESTAMP to datetime (assuming current date)
    # Since we only have HH:MM:SS, we'll use a reference date
    df["datetime"] = pd.to_datetime(df["TIMESTAMP"], format="%H:%M:%S")

    # Calculate statistics per timestamp
    print("Calculating CPU statistics by timestamp...")
    cpu_stats = (
        df.groupby("datetime")
        .agg({"CPU_PERCENT": ["mean", "median", "max", "std"]})
        .reset_index()
    )

    # Flatten column names
    cpu_stats.columns = ["datetime", "cpu_mean", "cpu_median", "cpu_max", "cpu_std"]

    # Sort by datetime
    cpu_stats = cpu_stats.sort_values("datetime")

    print(f"Creating time series plot with {len(cpu_stats)} time snapshots...")

    # Create figure with larger size for better visibility
    fig, ax = plt.subplots(figsize=(14, 6))

    # Plot different CPU metrics
    ax.plot(
        cpu_stats["datetime"],
        cpu_stats["cpu_mean"],
        label="Mean CPU %",
        linewidth=2,
        color="#1f77b4",
        alpha=0.8,
    )
    ax.plot(
        cpu_stats["datetime"],
        cpu_stats["cpu_median"],
        label="Median CPU %",
        linewidth=2,
        color="#ff7f0e",
        alpha=0.8,
    )
    ax.plot(
        cpu_stats["datetime"],
        cpu_stats["cpu_max"],
        label="Max CPU %",
        linewidth=2,
        color="#d62728",
        alpha=0.8,
    )

    # Fill area for std deviation around mean
    ax.fill_between(
        cpu_stats["datetime"],
        cpu_stats["cpu_mean"] - cpu_stats["cpu_std"],
        cpu_stats["cpu_mean"] + cpu_stats["cpu_std"],
        alpha=0.2,
        color="#1f77b4",
        label="Mean ± 1 Std Dev",
    )

    # Formatting
    ax.set_xlabel("Time (HH:MM:SS)", fontsize=12, fontweight="bold")
    ax.set_ylabel("CPU Percentage (%)", fontsize=12, fontweight="bold")
    ax.set_title(
        "CPU Usage Over Time - Process Metrics", fontsize=14, fontweight="bold"
    )
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3)

    # Format x-axis to show time nicely
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
    fig.autofmt_xdate(rotation=45, ha="right")

    # Set y-axis limits with some padding
    ax.set_ylim(bottom=0)

    # Tight layout to prevent label cutoff
    plt.tight_layout()

    # Save figure
    output_filename = Path(output_file).name
    output_dirpath = parquet_path.parent
    output_dirpath.parent.mkdir(parents=True, exist_ok=True)
    output_filepath = output_dirpath.joinpath(output_filename)
    plt.savefig(output_filepath, dpi=100, bbox_inches="tight")
    print(f"✓ Saved plot to {output_filepath}")
    print(f"  File size: {output_filepath.stat().st_size / 1024:.2f} KB")

    # Print statistics
    print(f"\nCPU Statistics:")
    print(f"  Mean CPU (avg):   {cpu_stats['cpu_mean'].mean():.2f}%")
    print(f"  Median CPU:       {cpu_stats['cpu_median'].mean():.2f}%")
    print(f"  Max CPU (max):    {cpu_stats['cpu_max'].max():.2f}%")
    print(f"  Min CPU (min):    {cpu_stats['cpu_max'].min():.2f}%")
    print(
        f"  Time range:       {cpu_stats['datetime'].min().strftime('%H:%M:%S')} - {cpu_stats['datetime'].max().strftime('%H:%M:%S')}"
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate a time series plot of CPU percentage from top data"
    )
    parser.add_argument(
        "parquet_file", help="Path to the parquet file with parsed top data"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="cpu-pct.png",
        help="Output PNG file path (default: cpu-pct.png)",
    )

    args = parser.parse_args()

    try:
        plot_cpu_timeseries(args.parquet_file, args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
