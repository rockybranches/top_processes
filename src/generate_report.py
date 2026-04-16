#!/usr/bin/env python3
"""
System Performance Analysis Report Generator

This script analyzes process monitoring data and generates a comprehensive markdown report
identifying the key factors contributing to CPU, memory, and I/O bound slowdowns, with
clear recommendations for system optimization.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import warnings
import sys
import click

warnings.filterwarnings("ignore")

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_PATH = (
    Path(__file__).parent.parent / "formatted_data" / "top_processes_120.parquet"
)
OUTPUT_DIR = Path(__file__).parent.parent / "report_output"
REPORT_PATH = OUTPUT_DIR / "system_performance_report.md"

# Create output directory
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================================
# DATA LOADING & PREPROCESSING
# ============================================================================


def load_data():
    """Load and validate the dataset."""
    df = pd.read_parquet(DATA_PATH)

    # Convert TIMESTAMP to datetime for analysis
    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], format="%H:%M:%S")

    return df


# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================


def analyze_cpu_bound(df):
    """Identify CPU-bound processes and patterns."""
    analysis = {}

    # Top CPU consumers by process
    cpu_by_cmd = (
        df.groupby("COMMAND")
        .agg({"CPU_PERCENT": ["mean", "max", "std", "count"]})
        .round(2)
    )
    cpu_by_cmd.columns = ["mean_cpu", "max_cpu", "std_cpu", "observations"]
    cpu_by_cmd = cpu_by_cmd[cpu_by_cmd["observations"] > 1].sort_values(
        "mean_cpu", ascending=False
    )

    analysis["top_cpu_commands"] = cpu_by_cmd.head(10)

    # Top CPU consumers by user
    cpu_by_user = (
        df.groupby("USER").agg({"CPU_PERCENT": ["mean", "max", "sum"]}).round(2)
    )
    cpu_by_user.columns = ["mean_cpu", "max_cpu", "total_cpu_hours"]
    cpu_by_user = cpu_by_user.sort_values("mean_cpu", ascending=False)

    analysis["cpu_by_user"] = cpu_by_user

    # Time-based CPU patterns (identify peak usage times)
    cpu_by_time = (
        df.groupby("TIMESTAMP")["CPU_PERCENT"].agg(["mean", "max", "sum"]).round(2)
    )
    analysis["cpu_time_series"] = cpu_by_time

    # Identify high-CPU spikes
    high_cpu_threshold = df["CPU_PERCENT"].quantile(0.95)
    high_cpu_processes = df[df["CPU_PERCENT"] > high_cpu_threshold][
        ["TIMESTAMP", "COMMAND", "USER", "CPU_PERCENT"]
    ].sort_values("CPU_PERCENT", ascending=False)
    analysis["high_cpu_processes"] = high_cpu_processes.head(20)
    analysis["high_cpu_threshold"] = high_cpu_threshold

    return analysis


def analyze_memory_bound(df):
    """Identify memory-bound processes and patterns."""
    analysis = {}

    # Top memory consumers by process
    mem_by_cmd = (
        df.groupby("COMMAND")
        .agg(
            {
                "MEM_PERCENT": ["mean", "max", "std"],
                "RES_MB": ["mean", "max"],
                "VIRT_MB": ["mean", "max"],
            }
        )
        .round(2)
    )
    mem_by_cmd.columns = [
        "mean_mem_pct",
        "max_mem_pct",
        "std_mem_pct",
        "mean_res_mb",
        "max_res_mb",
        "mean_virt_mb",
        "max_virt_mb",
    ]
    mem_by_cmd = mem_by_cmd.sort_values("mean_mem_pct", ascending=False)

    analysis["top_memory_commands"] = mem_by_cmd.head(10)

    # Top memory consumers by user
    mem_by_user = (
        df.groupby("USER")
        .agg({"MEM_PERCENT": ["mean", "max", "sum"], "RES_MB": ["mean", "max", "sum"]})
        .round(2)
    )
    mem_by_user.columns = [
        "mean_mem_pct",
        "max_mem_pct",
        "total_mem_pct",
        "mean_res_mb",
        "max_res_mb",
        "total_res_mb",
    ]
    mem_by_user = mem_by_user.sort_values("mean_mem_pct", ascending=False)

    analysis["memory_by_user"] = mem_by_user

    # Memory over time
    mem_by_time = (
        df.groupby("TIMESTAMP")
        .agg({"MEM_PERCENT": ["mean", "max", "sum"], "RES_MB": ["mean", "sum"]})
        .round(2)
    )
    mem_by_time.columns = [
        "mean_mem_pct",
        "max_mem_pct",
        "total_mem_pct",
        "mean_res_mb",
        "total_res_mb",
    ]
    analysis["memory_time_series"] = mem_by_time

    # High memory processes
    high_mem_threshold = df["MEM_PERCENT"].quantile(0.95)
    high_mem_processes = df[df["MEM_PERCENT"] > high_mem_threshold][
        ["TIMESTAMP", "COMMAND", "USER", "MEM_PERCENT", "RES_MB"]
    ].sort_values("MEM_PERCENT", ascending=False)
    analysis["high_memory_processes"] = high_mem_processes.head(20)
    analysis["high_mem_threshold"] = high_mem_threshold

    return analysis


def analyze_io_bound(df):
    """Identify I/O bound processes based on state analysis."""
    analysis = {}

    # Process states indicate I/O activity
    # D = Uninterruptible sleep (usually I/O wait)
    # S = Interruptible sleep
    # R = Running
    # I = Idle
    # Z = Zombie
    # T = Stopped

    state_distribution = df["STATE"].value_counts()
    analysis["state_distribution"] = state_distribution

    # Processes in D state (I/O wait)
    io_wait_processes = (
        df[df["STATE"] == "D"][["TIMESTAMP", "COMMAND", "USER", "PID"]]
        .drop_duplicates("COMMAND")
        .value_counts("COMMAND")
        .head(15)
    )
    analysis["io_wait_processes"] = io_wait_processes

    # By command: proportion in D state
    cmd_state_dist = df.groupby("COMMAND")["STATE"].value_counts().unstack(fill_value=0)
    if "D" in cmd_state_dist.columns:
        cmd_state_dist["D_percentage"] = (
            cmd_state_dist["D"] / cmd_state_dist.sum(axis=1) * 100
        ).round(2)
        io_bound_commands = cmd_state_dist.sort_values("D_percentage", ascending=False)[
            ["D_percentage"]
        ].head(10)
        analysis["io_bound_commands"] = io_bound_commands

    return analysis


def analyze_system_impact(df):
    """Analyze overall system impact and user-facing effects."""
    analysis = {}

    # Total system load
    total_cpu = df.groupby("TIMESTAMP")["CPU_PERCENT"].sum()
    total_mem = df.groupby("TIMESTAMP")["MEM_PERCENT"].sum()

    analysis["peak_system_cpu"] = total_cpu.max()
    analysis["mean_system_cpu"] = total_cpu.mean()
    analysis["peak_system_mem"] = total_mem.max()
    analysis["mean_system_mem"] = total_mem.mean()

    # Time periods with highest contention
    system_load = pd.DataFrame({"total_cpu": total_cpu, "total_mem": total_mem})
    system_load["cpu_rank"] = system_load["total_cpu"].rank(ascending=False)
    system_load["mem_rank"] = system_load["total_mem"].rank(ascending=False)
    system_load["combined_rank"] = system_load["cpu_rank"] + system_load["mem_rank"]

    analysis["high_contention_periods"] = system_load.nsmallest(5, "combined_rank")

    return analysis


def create_visualizations(df, analysis_cpu, analysis_memory, analysis_io):
    """Create all necessary visualizations."""

    # Set style
    plt.rcParams["figure.figsize"] = (14, 8)
    plt.rcParams["grid.linestyle"] = "--"
    plt.rcParams["grid.alpha"] = 0.3

    # ========== Figure 1: CPU Usage Over Time ==========
    fig, ax = plt.subplots(figsize=(14, 6))
    cpu_ts = df.groupby("TIMESTAMP")["CPU_PERCENT"].agg(["mean", "max", "std"])

    ax.plot(
        cpu_ts.index, cpu_ts["mean"], label="Mean CPU %", linewidth=2, color="#1f77b4"
    )
    ax.plot(
        cpu_ts.index,
        cpu_ts["max"],
        label="Max CPU %",
        linewidth=1.5,
        color="#d62728",
        alpha=0.7,
    )
    ax.fill_between(
        cpu_ts.index,
        cpu_ts["mean"] - cpu_ts["std"],
        cpu_ts["mean"] + cpu_ts["std"],
        alpha=0.3,
        color="#1f77b4",
        label="±1 Std Dev",
    )

    ax.set_xlabel("Time", fontsize=12, fontweight="bold")
    ax.set_ylabel("CPU Usage (%)", fontsize=12, fontweight="bold")
    ax.set_title(
        "System CPU Usage Over Time\n(Higher values indicate CPU-bound contention)",
        fontsize=13,
        fontweight="bold",
        pad=20,
    )
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_01_cpu_timeseries.png", dpi=100, bbox_inches="tight")
    plt.close()

    # ========== Figure 2: Top CPU Consuming Processes ==========
    fig, ax = plt.subplots(figsize=(12, 8))
    top_cpu = analysis_cpu["top_cpu_commands"].head(12)
    colors = plt.cm.get_cmap("RdYlGn")(np.linspace(0.4, 0.9, len(top_cpu)))

    bars = ax.barh(range(len(top_cpu)), top_cpu["mean_cpu"].values, color=colors)
    ax.set_yticks(range(len(top_cpu)))
    ax.set_yticklabels(top_cpu.index)
    ax.set_xlabel("Average CPU Usage (%)", fontsize=12, fontweight="bold")
    ax.set_title(
        "Top CPU-Consuming Processes\n(Processes causing CPU-bound slowdowns)",
        fontsize=13,
        fontweight="bold",
        pad=20,
    )
    ax.invert_yaxis()

    # Add value labels
    for i, (idx, row) in enumerate(top_cpu.iterrows()):
        ax.text(
            row["mean_cpu"],
            i,
            f" {row['mean_cpu']:.1f}%",
            va="center",
            fontweight="bold",
            fontsize=9,
        )

    plt.tight_layout()
    plt.savefig(
        OUTPUT_DIR / "fig_02_top_cpu_processes.png", dpi=100, bbox_inches="tight"
    )
    plt.close()

    # ========== Figure 3: Memory Usage Over Time ==========
    fig, ax = plt.subplots(figsize=(14, 6))
    mem_ts = df.groupby("TIMESTAMP")["MEM_PERCENT"].agg(["mean", "max", "std"])

    ax.plot(
        mem_ts.index,
        mem_ts["mean"],
        label="Mean Memory %",
        linewidth=2,
        color="#2ca02c",
    )
    ax.plot(
        mem_ts.index,
        mem_ts["max"],
        label="Max Memory %",
        linewidth=1.5,
        color="#ff7f0e",
        alpha=0.7,
    )
    ax.fill_between(
        mem_ts.index,
        mem_ts["mean"] - mem_ts["std"],
        mem_ts["mean"] + mem_ts["std"],
        alpha=0.3,
        color="#2ca02c",
        label="±1 Std Dev",
    )

    ax.set_xlabel("Time", fontsize=12, fontweight="bold")
    ax.set_ylabel("Memory Usage (%)", fontsize=12, fontweight="bold")
    ax.set_title(
        "System Memory Usage Over Time\n(Higher values indicate memory-bound contention)",
        fontsize=13,
        fontweight="bold",
        pad=20,
    )
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(
        OUTPUT_DIR / "fig_03_memory_timeseries.png", dpi=100, bbox_inches="tight"
    )
    plt.close()

    # ========== Figure 4: Top Memory Consuming Processes ==========
    fig, ax = plt.subplots(figsize=(12, 8))
    top_mem = analysis_memory["top_memory_commands"].head(12)
    colors = plt.cm.get_cmap("RdYlGn_r")(np.linspace(0.3, 0.9, len(top_mem)))

    bars = ax.barh(range(len(top_mem)), top_mem["mean_mem_pct"].values, color=colors)
    ax.set_yticks(range(len(top_mem)))
    ax.set_yticklabels(top_mem.index)
    ax.set_xlabel("Average Memory Usage (%)", fontsize=12, fontweight="bold")
    ax.set_title(
        "Top Memory-Consuming Processes\n(Processes causing memory-bound slowdowns)",
        fontsize=13,
        fontweight="bold",
        pad=20,
    )
    ax.invert_yaxis()

    # Add value labels
    for i, (idx, row) in enumerate(top_mem.iterrows()):
        ax.text(
            row["mean_mem_pct"],
            i,
            f" {row['mean_mem_pct']:.2f}%",
            va="center",
            fontweight="bold",
            fontsize=9,
        )

    plt.tight_layout()
    plt.savefig(
        OUTPUT_DIR / "fig_04_top_memory_processes.png", dpi=100, bbox_inches="tight"
    )
    plt.close()

    # ========== Figure 5: Process State Distribution ==========
    fig, ax = plt.subplots(figsize=(10, 6))
    state_dist = analysis_io["state_distribution"]
    state_labels = {
        "R": "Running",
        "S": "Interruptible Sleep",
        "D": "Uninterruptible Sleep (I/O Wait)",
        "I": "Idle",
        "Z": "Zombie",
        "T": "Stopped",
    }

    labels = [f"{state_labels.get(s, s)}\n({s})" for s in state_dist.index]
    colors_state = [
        "#d62728" if s == "D" else "#ff7f0e" if s == "R" else "#2ca02c"
        for s in state_dist.index
    ]

    result = ax.pie(
        state_dist.values,
        labels=labels,
        autopct="%1.1f%%",
        colors=colors_state,
        startangle=90,
        textprops={"fontsize": 10},
    )
    autotexts = result[2] if len(result) > 2 else []

    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontweight("bold")

    ax.set_title(
        "Process State Distribution\n(D=I/O Wait indicates I/O-bound slowdowns)",
        fontsize=13,
        fontweight="bold",
        pad=20,
    )
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_05_process_states.png", dpi=100, bbox_inches="tight")
    plt.close()

    # ========== Figure 6: CPU Usage by User ==========
    fig, ax = plt.subplots(figsize=(12, 7))
    cpu_by_user = analysis_cpu["cpu_by_user"].sort_values("mean_cpu", ascending=True)
    colors = plt.cm.get_cmap("tab10")(np.linspace(0.2, 0.8, min(len(cpu_by_user), 10)))

    bars = ax.barh(
        range(len(cpu_by_user)), cpu_by_user["mean_cpu"].values, color=colors
    )
    ax.set_yticks(range(len(cpu_by_user)))
    ax.set_yticklabels(cpu_by_user.index, fontsize=11)
    ax.set_xlabel("Average CPU Usage (%)", fontsize=12, fontweight="bold")
    ax.set_title(
        "CPU Usage by User Account\n(Identifies which users cause the most CPU contention)",
        fontsize=13,
        fontweight="bold",
        pad=20,
    )

    # Add value labels
    for i, (idx, row) in enumerate(cpu_by_user.iterrows()):
        ax.text(
            row["mean_cpu"],
            i,
            f" {row['mean_cpu']:.2f}%",
            va="center",
            fontweight="bold",
            fontsize=9,
        )

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_06_cpu_by_user.png", dpi=100, bbox_inches="tight")
    plt.close()

    # ========== Figure 7: Memory Usage by User ==========
    fig, ax = plt.subplots(figsize=(12, 7))
    mem_by_user = analysis_memory["memory_by_user"].sort_values(
        "mean_mem_pct", ascending=True
    )
    colors = plt.cm.get_cmap("tab10")(np.linspace(0.2, 0.8, min(len(mem_by_user), 10)))

    bars = ax.barh(
        range(len(mem_by_user)), mem_by_user["mean_mem_pct"].values, color=colors
    )
    ax.set_yticks(range(len(mem_by_user)))
    ax.set_yticklabels(mem_by_user.index, fontsize=11)
    ax.set_xlabel("Average Memory Usage (%)", fontsize=12, fontweight="bold")
    ax.set_title(
        "Memory Usage by User Account\n(Identifies which users cause the most memory contention)",
        fontsize=13,
        fontweight="bold",
        pad=20,
    )

    # Add value labels
    for i, (idx, row) in enumerate(mem_by_user.iterrows()):
        ax.text(
            row["mean_mem_pct"],
            i,
            f" {row['mean_mem_pct']:.2f}%",
            va="center",
            fontweight="bold",
            fontsize=9,
        )

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_07_memory_by_user.png", dpi=100, bbox_inches="tight")
    plt.close()

    print("✓ All visualizations generated successfully")


def generate_markdown_report(
    df, analysis_cpu, analysis_memory, analysis_io, analysis_system
):
    """Generate the markdown report."""

    report = []

    # Header
    report.append("# System Performance Analysis Report")
    report.append("")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("## Executive Summary")
    report.append("")
    report.append(
        "This report identifies the key system performance bottlenecks that would impact user"
    )
    report.append(
        "productivity and responsiveness. The analysis focuses on CPU-bound, memory-bound,"
    )
    report.append(
        "and I/O-bound slowdowns, along with recommendations for improvement."
    )
    report.append("")

    # Report Duration
    report.append("### Monitoring Period")
    timestamps = pd.to_datetime(df["TIMESTAMP"])
    report.append(f"- **Start Time:** {df['TIMESTAMP'].min()}")
    report.append(f"- **End Time:** {df['TIMESTAMP'].max()}")
    report.append(f"- **Duration:** ~40 minutes")
    report.append(f"- **Total Snapshots:** {df['TIMESTAMP'].nunique():,}")
    report.append(f"- **Total Records Analyzed:** {len(df):,}")
    report.append("")

    # ========================================================================
    # SECTION 1: CPU-BOUND SLOWDOWNS
    # ========================================================================
    report.append("---")
    report.append("")
    report.append("## 1. CPU-Bound Slowdowns")
    report.append("")
    report.append("### Impact on User Experience")
    report.append("")
    report.append(
        "**What it means:** CPU-bound slowdowns occur when processes consume significant CPU cycles,"
    )
    report.append(
        "leaving less compute capacity for user-facing applications. This causes:"
    )
    report.append("")
    report.append(
        "- **Unresponsive applications** - UI becomes sluggish, clicks/typing lag"
    )
    report.append("- **Slow application startup** - Applications take longer to launch")
    report.append(
        "- **Reduced interactivity** - Context switching between windows feels janky"
    )
    report.append("- **Terminal/CLI delays** - Command execution and output feel slow")
    report.append("")

    # System-wide CPU metrics
    report.append("### System-Wide CPU Usage")
    report.append("")
    report.append(f"- **Peak System CPU:** {analysis_system['peak_system_cpu']:.1f}%")
    report.append(
        f"- **Average System CPU:** {analysis_system['mean_system_cpu']:.2f}%"
    )
    report.append(
        f"- **Metric Interpretation:** Peak CPU >100% indicates multi-core usage; >200% suggests heavy multi-threaded workloads"
    )
    report.append("")

    report.append("### Figure 1: CPU Usage Over Time")
    report.append("![CPU Time Series](fig_01_cpu_timeseries.png)")
    report.append("")
    report.append(
        "The graph above shows CPU usage patterns throughout the monitoring period. Notable spikes indicate"
    )
    report.append(
        "periods of high computational activity where the system was under CPU pressure."
    )
    report.append("")

    # Top CPU processes
    report.append("### Top CPU-Consuming Processes")
    report.append("")
    report.append("**Figure 2: CPU Usage by Process**")
    report.append("![Top CPU Processes](fig_02_top_cpu_processes.png)")
    report.append("")

    report.append("**Detailed Breakdown:**")
    report.append("")
    report.append("| Process | Avg CPU % | Max CPU % | Observations |")
    report.append("|---------|-----------|-----------|--------------|")

    for cmd, row in analysis_cpu["top_cpu_commands"].head(10).iterrows():
        report.append(
            f"| {cmd} | {row['mean_cpu']:.2f}% | {row['max_cpu']:.2f}% | {int(row['observations'])} |"
        )

    report.append("")
    report.append("**Key Findings:**")
    top_cpu = analysis_cpu["top_cpu_commands"].iloc[0]
    if top_cpu["mean_cpu"] > 1.0:
        report.append(
            f"- **{analysis_cpu['top_cpu_commands'].index[0]}** is the primary CPU consumer, averaging {top_cpu['mean_cpu']:.2f}% CPU"
        )
        report.append(
            f"  - *User Impact:* This process competes with user applications for compute cycles"
        )
    else:
        report.append(
            f"- CPU usage is generally low (avg {analysis_cpu['cpu_by_user']['mean_cpu'].max():.2f}%), indicating minimal CPU contention"
        )

    report.append("")

    # CPU by user
    report.append("### CPU Usage by User Account")
    report.append("")
    report.append("**Figure 3: CPU Distribution by User**")
    report.append("![CPU by User](fig_06_cpu_by_user.png)")
    report.append("")

    report.append("| User | Avg CPU % | Max CPU % |")
    report.append("|------|-----------|-----------|")

    for user, row in analysis_cpu["cpu_by_user"].iterrows():
        report.append(f"| {user} | {row['mean_cpu']:.2f}% | {row['max_cpu']:.2f}% |")

    report.append("")
    report.append("**Key Insights:**")
    root_cpu = analysis_cpu["cpu_by_user"].loc["root", "mean_cpu"]
    report.append(f"- **root processes** account for {root_cpu:.2f}% average CPU usage")
    report.append(
        "- High root CPU usage typically comes from system daemons, kernel operations, and background tasks"
    )
    report.append("")

    # ========================================================================
    # SECTION 2: MEMORY-BOUND SLOWDOWNS
    # ========================================================================
    report.append("---")
    report.append("")
    report.append("## 2. Memory-Bound Slowdowns")
    report.append("")
    report.append("### Impact on User Experience")
    report.append("")
    report.append(
        "**What it means:** Memory pressure occurs when processes consume significant RAM, forcing"
    )
    report.append("the system to page data to disk. This causes:")
    report.append("")
    report.append(
        "- **Severe performance degradation** - Everything becomes very slow (10-100x slower)"
    )
    report.append(
        "- **Freezes and unresponsiveness** - System may appear hung for seconds/minutes"
    )
    report.append("- **High disk activity** - Constant swapping/paging to disk")
    report.append(
        "- **Out-of-memory crashes** - Applications may crash when memory is exhausted"
    )
    report.append("")

    # System-wide memory metrics
    report.append("### System-Wide Memory Usage")
    report.append("")
    report.append(
        f"- **Peak System Memory:** {analysis_system['peak_system_mem']:.2f}%"
    )
    report.append(
        f"- **Average System Memory:** {analysis_system['mean_system_mem']:.2f}%"
    )
    report.append(
        f"- **Memory Status:** {'⚠️ CRITICAL - High memory pressure' if analysis_system['peak_system_mem'] > 80 else '⚠️ WARNING - Moderate pressure' if analysis_system['peak_system_mem'] > 60 else '✓ Healthy - Low memory usage'}"
    )
    report.append("")

    report.append("### Figure 4: Memory Usage Over Time")
    report.append("![Memory Time Series](fig_03_memory_timeseries.png)")
    report.append("")
    report.append(
        "The graph above shows memory consumption patterns. Memory is typically slower to release,"
    )
    report.append("so persistent high memory indicates active processes hoarding RAM.")
    report.append("")

    # Top memory processes
    report.append("### Top Memory-Consuming Processes")
    report.append("")
    report.append("**Figure 5: Memory Usage by Process**")
    report.append("![Top Memory Processes](fig_04_top_memory_processes.png)")
    report.append("")

    report.append("**Detailed Breakdown (% of System Memory):**")
    report.append("")
    report.append("| Process | Avg Mem % | Max Mem % | Avg Resident MB |")
    report.append("|---------|-----------|-----------|-----------------|")

    for cmd, row in analysis_memory["top_memory_commands"].head(10).iterrows():
        report.append(
            f"| {cmd} | {row['mean_mem_pct']:.2f}% | {row['max_mem_pct']:.2f}% | {row['mean_res_mb']:.0f} MB |"
        )

    report.append("")
    report.append("**Key Findings:**")
    top_mem = analysis_memory["top_memory_commands"].iloc[0]
    if top_mem["mean_mem_pct"] > 2.0:
        report.append(
            f"- **{analysis_memory['top_memory_commands'].index[0]}** is the largest memory consumer at {top_mem['mean_mem_pct']:.2f}%"
        )
        report.append(
            f"  - *User Impact:* This process is holding significant system memory, potentially causing page thrashing"
        )

    report.append("")

    # Memory by user
    report.append("### Memory Usage by User Account")
    report.append("")
    report.append("**Figure 6: Memory Distribution by User**")
    report.append("![Memory by User](fig_07_memory_by_user.png)")
    report.append("")

    report.append("| User | Avg Mem % | Max Mem % | Total Resident MB |")
    report.append("|------|-----------|-----------|-------------------|")

    for user, row in analysis_memory["memory_by_user"].iterrows():
        report.append(
            f"| {user} | {row['mean_mem_pct']:.2f}% | {row['max_mem_pct']:.2f}% | {row['total_res_mb']:.0f} MB |"
        )

    report.append("")

    # ========================================================================
    # SECTION 3: I/O-BOUND SLOWDOWNS
    # ========================================================================
    report.append("---")
    report.append("")
    report.append("## 3. I/O-Bound Slowdowns")
    report.append("")
    report.append("### Impact on User Experience")
    report.append("")
    report.append(
        "**What it means:** I/O-bound slowdowns occur when processes wait for disk or network I/O."
    )
    report.append("This causes:")
    report.append("")
    report.append("- **Disk activity spikes** - High disk read/write load")
    report.append(
        "- **File operation delays** - Opening, saving, or copying files becomes slow"
    )
    report.append("- **Network latency** - Network operations stall")
    report.append(
        "- **System-wide slowness** - Even fast processes can slow down due to I/O queue congestion"
    )
    report.append("")

    report.append("### Process State Analysis")
    report.append("")
    report.append("Processes in different states indicate resource contention:")
    report.append("")
    report.append("- **R (Running)** - Actively executing on CPU")
    report.append(
        "- **S (Interruptible Sleep)** - Waiting for events (usually responsive)"
    )
    report.append(
        "- **D (Uninterruptible Sleep)** - Waiting for I/O operations (⚠️ KEY INDICATOR OF I/O WAIT)"
    )
    report.append("- **I (Idle)** - Not consuming resources")
    report.append("- **Z (Zombie)** - Process has exited but parent hasn't cleaned up")
    report.append("- **T (Stopped)** - Manually stopped by debugger or signal")
    report.append("")

    report.append("### Figure 7: Process State Distribution")
    report.append("![Process States](fig_05_process_states.png)")
    report.append("")

    # State distribution table
    report.append("**State Distribution:**")
    report.append("")
    report.append("| State | Count | Percentage | Meaning |")
    report.append("|-------|-------|-----------|---------|")

    state_labels = {
        "R": "Running on CPU",
        "S": "Interruptible sleep",
        "D": "I/O wait (uninterruptible)",
        "I": "Idle",
        "Z": "Zombie process",
        "T": "Stopped",
    }

    total = analysis_io["state_distribution"].sum()
    for state in ["D", "R", "S", "I", "Z", "T"]:
        if state in analysis_io["state_distribution"].index:
            count = analysis_io["state_distribution"][state]
            pct = count / total * 100
            report.append(
                f"| {state} | {int(count):,} | {pct:.1f}% | {state_labels[state]} |"
            )

    report.append("")

    # I/O bound processes
    if not analysis_io["io_bound_commands"].empty:
        report.append("### Processes in I/O Wait (D State)")
        report.append("")
        report.append(
            "These processes spend time waiting for disk I/O, indicating heavy file system or storage activity:"
        )
        report.append("")
        report.append("| Process | Time in I/O Wait % |")
        report.append("|---------|-------------------|")

        for cmd, row in analysis_io["io_bound_commands"].head(10).iterrows():
            report.append(f"| {cmd} | {row['D_percentage']:.1f}% |")

        report.append("")

    # ========================================================================
    # SECTION 4: SUMMARY & RECOMMENDATIONS
    # ========================================================================
    report.append("---")
    report.append("")
    report.append("## 4. System Impact Summary")
    report.append("")

    # Identify primary bottleneck
    report.append("### Primary Bottleneck Identification")
    report.append("")

    peak_cpu = analysis_system["peak_system_cpu"]
    peak_mem = analysis_system["peak_system_mem"]
    high_io_wait = (
        analysis_io["state_distribution"].get("D", 0)
        / analysis_io["state_distribution"].sum()
        * 100
    )

    bottlenecks = []
    if peak_cpu > 100:
        bottlenecks.append(f"**CPU Bound** (peak {peak_cpu:.0f}%)")
    if peak_mem > 50:
        bottlenecks.append(f"**Memory Bound** (peak {peak_mem:.1f}%)")
    if high_io_wait > 5:
        bottlenecks.append(f"**I/O Bound** ({high_io_wait:.1f}% in wait state)")

    if not bottlenecks:
        report.append(
            "✓ **System is healthy** - No significant bottlenecks detected during monitoring period"
        )
    else:
        report.append("⚠️ **Identified Bottlenecks:**")
        for bottleneck in bottlenecks:
            report.append(f"- {bottleneck}")

    report.append("")

    # Detailed impact analysis
    report.append("### User-Facing Impact Analysis")
    report.append("")

    # CPU impact
    report.append("#### CPU-Bound Impact (User Responsiveness)")
    if analysis_cpu["cpu_by_user"]["mean_cpu"].max() > 2.0:
        report.append(
            "- 🔴 **HIGH IMPACT** - User processes significantly competing with background tasks"
        )
    elif analysis_cpu["cpu_by_user"]["mean_cpu"].max() > 0.5:
        report.append("- 🟡 **MODERATE IMPACT** - Some CPU contention observed")
    else:
        report.append("- 🟢 **LOW IMPACT** - Ample CPU headroom for user applications")

    report.append("")

    # Memory impact
    report.append("#### Memory-Bound Impact (System Responsiveness)")
    if analysis_system["peak_system_mem"] > 80:
        report.append(
            "- 🔴 **CRITICAL** - Memory pressure likely causing disk paging and severe slowdowns"
        )
    elif analysis_system["peak_system_mem"] > 60:
        report.append(
            "- 🟡 **WARNING** - Moderate memory pressure; system may experience occasional slowdowns"
        )
    else:
        report.append(
            "- 🟢 **HEALTHY** - Sufficient memory available; no memory-bound slowdowns"
        )

    report.append("")

    # I/O impact
    report.append("#### I/O-Bound Impact (File System Operations)")
    if high_io_wait > 10:
        report.append(
            "- 🔴 **HIGH IMPACT** - Significant I/O wait; disk operations are bottleneck"
        )
    elif high_io_wait > 5:
        report.append("- 🟡 **MODERATE IMPACT** - Notable I/O wait detected")
    else:
        report.append("- 🟢 **LOW IMPACT** - I/O performance is good")

    report.append("")

    # ========================================================================
    # RECOMMENDATIONS
    # ========================================================================
    report.append("---")
    report.append("")
    report.append("## 5. Recommendations")
    report.append("")
    report.append("### Priority Actions")
    report.append("")

    top_processes = analysis_cpu["top_cpu_commands"].index[0]
    top_memory = analysis_memory["top_memory_commands"].index[0]

    report.append("1. **Monitor Top Processes**")
    report.append(f"   - Watch `{top_processes}` (highest CPU consumer)")
    report.append(f"   - Watch `{top_memory}` (highest memory consumer)")
    report.append("   - Use: `top`, `htop`, or `ps` to monitor in real-time")
    report.append("")

    report.append("2. **Reduce Background Task Load**")
    report.append("   - Consider disabling non-essential background services")
    report.append("   - Schedule heavy computational tasks during off-hours")
    report.append("   - Use cgroups or cpulimit to restrict resource usage")
    report.append("")

    if analysis_system["peak_system_mem"] > 60:
        report.append("3. **Address Memory Pressure**")
        report.append("   - Review and limit memory consumption of large processes")
        report.append("   - Consider increasing swap or installing additional RAM")
        report.append("   - Use: `free -h`, `vmstat`, `sar -r` to monitor memory")
        report.append("")

    if high_io_wait > 5:
        report.append("3. **Optimize I/O Operations**")
        report.append("   - Check disk health: `iostat -x`, `iotop`")
        report.append("   - Look for excessive read/write activity")
        report.append("   - Consider SSD upgrade if using HDD")
        report.append("")

    report.append("4. **System Monitoring Setup**")
    report.append(
        "   - Deploy continuous monitoring: `collectd`, `telegraf`, `prometheus`"
    )
    report.append("   - Set alerts for resource thresholds")
    report.append("   - Create performance baselines for comparison")
    report.append("")

    report.append("### Advanced Diagnostics")
    report.append("")
    report.append("```bash")
    report.append("# Real-time process monitoring")
    report.append("htop")
    report.append("")
    report.append("# CPU profiling")
    report.append("perf top")
    report.append("")
    report.append("# Memory analysis")
    report.append("free -h && vmstat 2")
    report.append("")
    report.append("# I/O monitoring")
    report.append("iostat -x 1 && iotop -o")
    report.append("")
    report.append("# System-wide profiling")
    report.append("sar -u 1 20  # CPU usage")
    report.append("sar -r 1 20  # Memory usage")
    report.append("sar -d 1 20  # Disk I/O")
    report.append("```")
    report.append("")

    # ========================================================================
    # TECHNICAL NOTES
    # ========================================================================
    report.append("---")
    report.append("")
    report.append("## Technical Notes")
    report.append("")
    report.append("### Methodology")
    report.append("")
    report.append(
        "- **Data Source:** `top` command output sampled at regular intervals"
    )
    report.append(
        "- **Analysis Window:** All processes captured during monitoring period"
    )
    report.append("- **Metrics Aggregated:** Mean, max, and sum across all samples")
    report.append("- **Threshold Used:** 95th percentile for outlier identification")
    report.append("")

    report.append("### Metric Definitions")
    report.append("")
    report.append(
        "- **CPU %:** Percentage of one CPU core (100% = full utilization of one core)"
    )
    report.append("- **MEM %:** Percentage of total system RAM")
    report.append("- **RES (Resident):** Physical RAM currently allocated to process")
    report.append(
        "- **VIRT (Virtual):** Total virtual memory address space (includes swapped/mapped)"
    )
    report.append("")

    report.append("### State Codes Explained")
    report.append("")
    report.append(
        "- **D:** Uninterruptible sleep (usually I/O wait) - Process cannot be interrupted"
    )
    report.append("- **R:** Running - Currently executing or queued to run")
    report.append(
        "- **S:** Interruptible sleep - Waiting for event (can be interrupted)"
    )
    report.append("- **I:** Idle - Sleeping and uninterruptible")
    report.append("- **Z:** Zombie - Exited but parent process hasn't cleaned up")
    report.append("- **T:** Stopped - Paused by debugger or job control")
    report.append("")

    report.append("---")
    report.append("")
    report.append(
        "**Report Complete** | Generated automatically by `generate_report.py`"
    )

    return "\n".join(report)


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def run_full_analysis(verbose=True):
    """Run the complete analysis pipeline."""
    if verbose:
        print("\n" + "=" * 70)
        print("SYSTEM PERFORMANCE ANALYSIS REPORT GENERATOR")
        print("=" * 70 + "\n")

    # Load data
    if verbose:
        print("📊 Loading data...")
    df = load_data()
    if verbose:
        print(
            f"   ✓ Loaded {len(df):,} records from {df['TIMESTAMP'].nunique()} snapshots\n"
        )

    # Run analyses
    if verbose:
        print("🔍 Running analyses...")
        print("   • CPU-bound analysis...", end=" ", flush=True)
    analysis_cpu = analyze_cpu_bound(df)
    if verbose:
        print("✓")

    if verbose:
        print("   • Memory-bound analysis...", end=" ", flush=True)
    analysis_memory = analyze_memory_bound(df)
    if verbose:
        print("✓")

    if verbose:
        print("   • I/O-bound analysis...", end=" ", flush=True)
    analysis_io = analyze_io_bound(df)
    if verbose:
        print("✓")

    if verbose:
        print("   • System impact analysis...", end=" ", flush=True)
    analysis_system = analyze_system_impact(df)
    if verbose:
        print("✓\n")

    # Create visualizations
    if verbose:
        print("📈 Creating visualizations...")
    create_visualizations(df, analysis_cpu, analysis_memory, analysis_io)
    if verbose:
        print("")

    # Generate report
    if verbose:
        print("📝 Generating markdown report...")
    report_content = generate_markdown_report(
        df, analysis_cpu, analysis_memory, analysis_io, analysis_system
    )

    # Save report
    with open(REPORT_PATH, "w") as f:
        f.write(report_content)

    if verbose:
        print(f"   ✓ Report saved to: {REPORT_PATH}\n")

    return analysis_cpu, analysis_memory, analysis_io, analysis_system


@click.group()
def cli():
    """System Performance Analysis Report Generator CLI.

    Analyze process monitoring data and generate comprehensive performance reports
    with visualizations and recommendations.
    """
    pass


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=str(REPORT_PATH),
    help=f"Output path for the report (default: {REPORT_PATH})",
)
@click.option(
    "--data",
    "-d",
    type=click.Path(exists=True),
    default=str(DATA_PATH),
    help=f"Path to input data file (default: {DATA_PATH})",
)
def generate(output, data):
    """Generate a complete performance analysis report with visualizations."""
    global DATA_PATH, REPORT_PATH
    DATA_PATH = Path(data)
    REPORT_PATH = Path(output)

    try:
        analysis_cpu, analysis_memory, analysis_io, analysis_system = run_full_analysis(
            verbose=True
        )

        # Summary statistics
        print("=" * 70)
        print("REPORT SUMMARY")
        print("=" * 70)
        print(f"\n📊 Peak System CPU:     {analysis_system['peak_system_cpu']:.1f}%")
        print(f"📊 Average System CPU:  {analysis_system['mean_system_cpu']:.2f}%")
        print(f"🧠 Peak System Memory:  {analysis_system['peak_system_mem']:.2f}%")
        print(f"🧠 Average Memory:      {analysis_system['mean_system_mem']:.2f}%")

        io_wait_pct = (
            analysis_io["state_distribution"].get("D", 0)
            / analysis_io["state_distribution"].sum()
            * 100
        )
        print(f"⏳ I/O Wait Processes:  {io_wait_pct:.1f}%")

        print(
            f"\n📌 Top CPU Process:     {analysis_cpu['top_cpu_commands'].index[0]} ({analysis_cpu['top_cpu_commands'].iloc[0]['mean_cpu']:.2f}% avg)"
        )
        print(
            f"📌 Top Memory Process:  {analysis_memory['top_memory_commands'].index[0]} ({analysis_memory['top_memory_commands'].iloc[0]['mean_mem_pct']:.2f}% avg)"
        )

        print(f"\n✅ Report generated successfully!")
        print(f"📁 Output directory:    {OUTPUT_DIR}")
        print(f"📄 Main report:         {REPORT_PATH.name}")
        print(f"📊 Figures generated:   7 high-quality PNG visualizations\n")
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
def summary():
    """Display a quick summary of system metrics without generating full report."""
    try:
        df = load_data()

        click.echo("\n" + "=" * 70)
        click.echo("SYSTEM PERFORMANCE SUMMARY")
        click.echo("=" * 70 + "\n")

        # Quick metrics
        click.echo(f"📊 Data Coverage:")
        click.echo(f"   • Records: {len(df):,}")
        click.echo(f"   • Snapshots: {df['TIMESTAMP'].nunique()}")
        click.echo(
            f"   • Time Range: {df['TIMESTAMP'].min()} to {df['TIMESTAMP'].max()}"
        )
        click.echo(f"   • Unique Processes: {df['COMMAND'].nunique()}")
        click.echo(f"   • Unique Users: {df['USER'].nunique()}\n")

        # CPU metrics
        click.echo(f"📊 CPU Metrics:")
        click.echo(f"   • Peak: {df['CPU_PERCENT'].max():.1f}%")
        click.echo(f"   • Mean: {df['CPU_PERCENT'].mean():.2f}%")
        click.echo(f"   • Std Dev: {df['CPU_PERCENT'].std():.2f}%\n")

        # Memory metrics
        click.echo(f"🧠 Memory Metrics:")
        click.echo(f"   • Peak: {df['MEM_PERCENT'].max():.2f}%")
        click.echo(f"   • Mean: {df['MEM_PERCENT'].mean():.2f}%")
        click.echo(f"   • Std Dev: {df['MEM_PERCENT'].std():.2f}%\n")

        # State distribution
        click.echo(f"📋 Process States:")
        state_dist = df["STATE"].value_counts()
        state_labels = {
            "R": "Running",
            "S": "Interruptible Sleep",
            "D": "Uninterruptible Sleep (I/O Wait)",
            "I": "Idle",
            "Z": "Zombie",
            "T": "Stopped",
        }
        total = state_dist.sum()
        for state in ["R", "S", "D", "I", "Z", "T"]:
            if state in state_dist.index:
                count = state_dist[state]
                pct = count / total * 100
                click.echo(
                    f"   • {state_labels.get(state, state):30s} {count:7,d} ({pct:5.1f}%)"
                )

        click.echo("")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--top-n",
    "-n",
    type=int,
    default=10,
    help="Number of top processes to display (default: 10)",
)
def top_processes(top_n):
    """Show top CPU and memory consuming processes."""
    try:
        df = load_data()

        # Top CPU processes
        click.echo("\n" + "=" * 70)
        click.echo("TOP CPU-CONSUMING PROCESSES")
        click.echo("=" * 70 + "\n")

        cpu_by_cmd = (
            df.groupby("COMMAND")
            .agg({"CPU_PERCENT": ["mean", "max", "std", "count"]})
            .round(2)
        )
        cpu_by_cmd.columns = ["mean_cpu", "max_cpu", "std_cpu", "observations"]
        cpu_by_cmd = cpu_by_cmd[cpu_by_cmd["observations"] > 1].sort_values(
            "mean_cpu", ascending=False
        )

        click.echo(f"{'Process':<35s} {'Avg CPU':<12s} {'Max CPU':<12s} {'Count':<8s}")
        click.echo("-" * 70)
        for cmd, row in cpu_by_cmd.head(top_n).iterrows():
            click.echo(
                f"{cmd:<35s} {row['mean_cpu']:>10.2f}% {row['max_cpu']:>10.2f}% {int(row['observations']):>7,d}"
            )

        # Top Memory processes
        click.echo("\n" + "=" * 70)
        click.echo("TOP MEMORY-CONSUMING PROCESSES")
        click.echo("=" * 70 + "\n")

        mem_by_cmd = (
            df.groupby("COMMAND")
            .agg({"MEM_PERCENT": ["mean", "max"], "RES_MB": ["mean", "max"]})
            .round(2)
        )
        mem_by_cmd.columns = ["mean_mem", "max_mem", "mean_res", "max_res"]
        mem_by_cmd = mem_by_cmd.sort_values("mean_mem", ascending=False)

        click.echo(
            f"{'Process':<35s} {'Avg Mem %':<12s} {'Max Mem %':<12s} {'Avg RES MB':<15s}"
        )
        click.echo("-" * 75)
        for cmd, row in mem_by_cmd.head(top_n).iterrows():
            click.echo(
                f"{cmd:<35s} {row['mean_mem']:>10.2f}% {row['max_mem']:>10.2f}% {row['mean_res']:>13.0f} MB"
            )

        click.echo("")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
def check_bottlenecks():
    """Identify and report system bottlenecks."""
    try:
        df = load_data()

        click.echo("\n" + "=" * 70)
        click.echo("BOTTLENECK ANALYSIS")
        click.echo("=" * 70 + "\n")

        # Analyze bottlenecks
        analysis_cpu = analyze_cpu_bound(df)
        analysis_memory = analyze_memory_bound(df)
        analysis_io = analyze_io_bound(df)
        analysis_system = analyze_system_impact(df)

        peak_cpu = analysis_system["peak_system_cpu"]
        peak_mem = analysis_system["peak_system_mem"]
        high_io_wait = (
            analysis_io["state_distribution"].get("D", 0)
            / analysis_io["state_distribution"].sum()
            * 100
        )

        bottlenecks = []
        if peak_cpu > 100:
            bottlenecks.append(
                (
                    "CPU-Bound",
                    f"Peak {peak_cpu:.0f}%",
                    "🔴 CRITICAL" if peak_cpu > 300 else "🟡 WARNING",
                )
            )
        if peak_mem > 50:
            bottlenecks.append(
                (
                    "Memory-Bound",
                    f"Peak {peak_mem:.1f}%",
                    "🔴 CRITICAL" if peak_mem > 80 else "🟡 WARNING",
                )
            )
        if high_io_wait > 5:
            bottlenecks.append(
                (
                    "I/O-Bound",
                    f"{high_io_wait:.1f}% in D state",
                    "🔴 HIGH" if high_io_wait > 10 else "🟡 MODERATE",
                )
            )

        if not bottlenecks:
            click.echo("✓ No significant bottlenecks detected!\n")
        else:
            click.echo(f"{'Type':<20s} {'Metric':<20s} {'Severity':<15s}")
            click.echo("-" * 55)
            for btype, metric, severity in bottlenecks:
                click.echo(f"{btype:<20s} {metric:<20s} {severity:<15s}")
            click.echo("")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=str(OUTPUT_DIR),
    help=f"Output directory for visualizations (default: {OUTPUT_DIR})",
)
@click.option(
    "--data",
    "-d",
    type=click.Path(exists=True),
    default=str(DATA_PATH),
    help=f"Path to input data file (default: {DATA_PATH})",
)
def visualize(output_dir, data):
    """Generate visualization charts only (no markdown report)."""
    global DATA_PATH, OUTPUT_DIR
    DATA_PATH = Path(data)
    OUTPUT_DIR = Path(output_dir)
    OUTPUT_DIR.mkdir(exist_ok=True)

    try:
        click.echo("\n📈 Generating visualizations...\n")
        df = load_data()
        analysis_cpu = analyze_cpu_bound(df)
        analysis_memory = analyze_memory_bound(df)
        analysis_io = analyze_io_bound(df)

        create_visualizations(df, analysis_cpu, analysis_memory, analysis_io)
        click.echo(f"✅ Visualizations saved to: {OUTPUT_DIR}\n")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
