#!/usr/bin/env python3
"""
CLI script to generate raw top_processes.out dataset from the current system.

This script captures process data from the 'top' command at regular intervals
and saves it to a raw output file. The output can then be parsed using
parse_top_processes.py to generate a parquet dataset for analysis.

Usage:
    .venv/bin/python3 src/generate_raw_dataset.py [--duration 60] [--interval 1] [--output raw_top_processes.out]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime


def generate_raw_dataset(
    output_path: str = "raw_top_processes.out",
    duration: int = 60,
    interval: int = 1,
) -> None:
    """
    Generate raw top command output by capturing system process data.

    Args:
        output_path: Path where to save the raw output file
        duration: Total duration in seconds to capture data (default: 60)
        interval: Interval in seconds between captures (default: 1)

    Raises:
        RuntimeError: If 'top' command is not available or fails
    """
    output_file = Path(output_path).resolve()

    # Validate arguments
    if duration < 1 or interval < 1:
        raise ValueError("Duration and interval must be at least 1 second")

    if interval > duration:
        raise ValueError("Interval cannot be greater than duration")

    num_snapshots = max(1, duration // interval)

    print(f"{'=' * 70}")
    print("RAW TOP DATASET GENERATOR")
    print(f"{'=' * 70}\n")
    print(f"📊 Configuration:")
    print(f"   Output file:    {output_file}")
    print(f"   Duration:       {duration} seconds")
    print(f"   Interval:       {interval} second(s)")
    print(f"   Snapshots:      ~{num_snapshots}")
    print(f"\n{'=' * 70}\n")

    # Check if top command exists
    try:
        subprocess.run(["which", "top"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("❌ Error: 'top' command not found on this system")
        sys.exit(1)

    # Create parent directory if needed
    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Start capturing top output
        with open(output_file, "w") as f:
            print(f"⏱️  Starting capture...\n")

            start_time = time.time()
            snapshot_count = 0

            while True:
                elapsed = time.time() - start_time

                if elapsed > duration:
                    break

                try:
                    # Run top in batch mode (-b) for one iteration (-n 1)
                    result = subprocess.run(
                        ["top", "-bn1"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )

                    if result.returncode == 0:
                        f.write(result.stdout)
                        snapshot_count += 1

                        # Print progress
                        progress_pct = min(100, int((elapsed / duration) * 100))
                        print(
                            f"   ✓ Snapshot {snapshot_count:3d} "
                            f"@ {elapsed:6.1f}s ({progress_pct:3d}%) "
                            f"[{output_file.name}]"
                        )

                    else:
                        print(
                            f"   ⚠️  Warning: 'top' failed on iteration "
                            f"{snapshot_count + 1}"
                        )

                except subprocess.TimeoutExpired:
                    print(
                        f"   ⚠️  Warning: 'top' command timed out on "
                        f"iteration {snapshot_count + 1}"
                    )

                # Sleep for the specified interval
                remaining = duration - (time.time() - start_time)
                if remaining > 0:
                    sleep_time = min(interval, remaining)
                    time.sleep(sleep_time)

        # Final report
        total_time = time.time() - start_time
        file_size = output_file.stat().st_size / (1024 * 1024)  # Convert to MB

        print(f"\n{'=' * 70}")
        print("✅ CAPTURE COMPLETE")
        print(f"{'=' * 70}\n")
        print(f"📊 Results:")
        print(f"   Snapshots captured:  {snapshot_count}")
        print(f"   Total time:          {total_time:.1f} seconds")
        print(f"   Output file:         {output_file}")
        print(f"   File size:           {file_size:.2f} MB")
        print(f"\n📝 Next steps:")
        print(
            f"   1. Parse the data: "
            f".venv/bin/python3 src/parse_top_processes.py {output_path}"
        )
        print(f"   2. Generate report: .venv/bin/python3 src/generate_report.py")
        print(f"\n{'=' * 70}\n")

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Capture interrupted by user after {snapshot_count} snapshots")
        file_size = output_file.stat().st_size / (1024 * 1024)
        print(f"   Output saved to: {output_file} ({file_size:.2f} MB)\n")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error during capture: {e}\n")
        sys.exit(1)


def main():
    """Parse CLI arguments and generate the dataset."""
    parser = argparse.ArgumentParser(
        description="Generate raw top command output dataset for process analysis",
        epilog=(
            "Example: .venv/bin/python3 src/generate_raw_dataset.py "
            "--duration 120 --interval 2"
        ),
    )

    parser.add_argument(
        "-o",
        "--output",
        default="raw_top_processes.out",
        help="Output file path (default: raw_top_processes.out)",
    )

    parser.add_argument(
        "-d",
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds to capture data (default: 60)",
    )

    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=1,
        help="Interval in seconds between captures (default: 1)",
    )

    args = parser.parse_args()

    try:
        generate_raw_dataset(
            output_path=args.output,
            duration=args.duration,
            interval=args.interval,
        )
    except ValueError as e:
        print(f"❌ Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
