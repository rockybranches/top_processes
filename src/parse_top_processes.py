#!/usr/bin/env python3
"""
CLI script to parse top command output and export to parquet format.
Handles multiple time-binned snapshots from top output.
"""

import argparse
import re
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd


def parse_timestamp_from_header(header_line: str):
    """
    Extract timestamp from top header line.

    Args:
        header_line: Line starting with "top - HH:MM:SS ..."

    Returns:
        Timestamp string in format HH:MM:SS or None
    """
    match = re.search(r"top - (\d{2}:\d{2}:\d{2})", header_line)
    if match:
        return match.group(1)
    return None


def parse_top_output(file_path: str) -> pd.DataFrame:
    """
    Parse top command output with time-binned snapshots and return as a DataFrame.

    Args:
        file_path: Path to the raw top output file

    Returns:
        DataFrame containing parsed process data with timestamp for each snapshot
    """
    file_path_obj = Path(file_path)

    if not file_path_obj.exists():
        raise FileNotFoundError(f"Input file not found: {file_path_obj}")

    with open(file_path_obj, "r") as f:
        lines = f.readlines()

    # Identify snapshot boundaries (lines starting with "top -")
    snapshot_boundaries = []
    for i, line in enumerate(lines):
        if line.strip().startswith("top -"):
            snapshot_boundaries.append(i)

    if not snapshot_boundaries:
        raise ValueError("No snapshot boundaries found (no 'top -' header lines)")

    # Add the end of file as a boundary
    snapshot_boundaries.append(len(lines))

    # Parse each snapshot
    all_data = []

    for snap_idx in range(len(snapshot_boundaries) - 1):
        start_idx = snapshot_boundaries[snap_idx]
        end_idx = snapshot_boundaries[snap_idx + 1]

        # Extract timestamp from header
        timestamp = parse_timestamp_from_header(lines[start_idx])

        if timestamp is None:
            continue

        # Find the column header line for this snapshot
        header_idx = None
        for i in range(start_idx, end_idx):
            if "PID" in lines[i] and "USER" in lines[i]:
                header_idx = i
                break

        if header_idx is None:
            continue

        # Parse process data rows for this snapshot
        for line in lines[header_idx + 1 : end_idx]:
            line = line.strip()
            if (
                not line
                or line.startswith("top -")
                or "Tasks:" in line
                or "%Cpu" in line
                or "MiB" in line
            ):
                continue

            # Split by whitespace, but need to handle the COMMAND column which may have spaces
            parts = line.split()

            if len(parts) < 11:  # Minimum fields needed
                continue

            # Extract numeric columns
            try:
                pid = int(parts[0])
                user = parts[1]
                pr = int(parts[2])
                ni = int(parts[3])
                virt = parse_memory(parts[4])
                res = parse_memory(parts[5])
                shr = parse_memory(parts[6])
                state = parts[7]
                cpu_percent = float(parts[8])
                mem_percent = float(parts[9])
                time_str = parts[10]
                command = " ".join(parts[11:])  # COMMAND can have spaces

                all_data.append(
                    {
                        "TIMESTAMP": timestamp,
                        "PID": pid,
                        "USER": user,
                        "PR": pr,
                        "NI": ni,
                        "VIRT_MB": virt,
                        "RES_MB": res,
                        "SHR_MB": shr,
                        "STATE": state,
                        "CPU_PERCENT": cpu_percent,
                        "MEM_PERCENT": mem_percent,
                        "TIME": time_str,
                        "COMMAND": command,
                    }
                )
            except (ValueError, IndexError) as e:
                # Skip lines that can't be parsed
                continue

    if not all_data:
        raise ValueError("No valid data rows found in file")

    return pd.DataFrame(all_data)


def parse_memory(mem_str: str) -> float:
    """
    Parse memory string (e.g., '257.0g', '409.3m', '0.0m') to MB.

    Args:
        mem_str: Memory string with unit suffix

    Returns:
        Memory in MB as float
    """
    match = re.match(r"([\d.]+)([gmk]?)", mem_str.lower())
    if not match:
        return 0.0

    value = float(match.group(1))
    unit = match.group(2)

    if unit == "g":
        return value * 1024  # GB to MB
    elif unit == "m":
        return value
    elif unit == "k":
        return value / 1024  # KB to MB
    else:
        return value  # Assume MB


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Parse top command output and export to parquet format"
    )
    parser.add_argument("input_file", help="Path to the raw top output file")
    parser.add_argument(
        "-o",
        "--output",
        default="formatted_data/top_processes.parquet",
        help="Output parquet file path (default: formatted_data/top_processes.parquet)",
    )

    args = parser.parse_args()

    try:
        print(f"Parsing {args.input_file}...")
        df = parse_top_output(args.input_file)
        print(f"Parsed {len(df)} process records")

        # Create output directory if it doesn't exist
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Export to parquet
        df.to_parquet(args.output, index=False)
        print(f"Successfully exported to {args.output}")
        print(f"File size: {output_path.stat().st_size / 1024:.2f} KB")

        # Print data info
        print(f"\nDataFrame shape: {df.shape}")
        print(f"\nColumn types:\n{df.dtypes}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
