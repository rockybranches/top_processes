# System Performance Analysis Report Generator

## Overview

This is a **production-ready Python script** that analyzes system process monitoring data and generates a comprehensive markdown report with embedded visualizations. The script identifies key performance bottlenecks and their user-facing impact.

### Quick Facts
- **Lines of Code:** 1,116 (well-structured, documented)
- **Dependencies:** pandas, numpy, matplotlib, pyarrow
- **Runtime:** ~2-3 seconds for 320K records
- **Output Size:** 484 KB (report + 7 visualizations)
- **Report Format:** Markdown with embedded PNG figures

---

## What Problem Does It Solve?

When a user complains the system is "slow," it could be due to:

1. **CPU-Bound Slowdowns** - CPU cores maxed out
   - Symptom: Applications are unresponsive, UI lags
   - Cause: Heavy computational work

2. **Memory-Bound Slowdowns** - RAM full, disk paging occurring
   - Symptom: System freezes for seconds/minutes
   - Cause: Too many large applications running

3. **I/O-Bound Slowdowns** - Disk/network waiting
   - Symptom: File operations are slow
   - Cause: Disk reads/writes or network delays

**This script identifies which of these is happening and quantifies the impact.**

---

## Script Architecture

### Main Functions

```
load_data()
├─ Loads parquet file
└─ Parses timestamps

analyze_cpu_bound(df)
├─ Top CPU processes
├─ CPU per user
├─ Time-series trends
└─ High CPU outliers (95th percentile)

analyze_memory_bound(df)
├─ Top memory processes
├─ Memory per user
├─ Resident memory analysis
└─ Memory pressure trends

analyze_io_bound(df)
├─ Process state distribution
├─ I/O wait detection
├─ Identify processes in D state
└─ Calculate I/O bound %

analyze_system_impact(df)
├─ Peak/average metrics
├─ Contention periods
└─ Combined impact analysis

create_visualizations(df, analyses)
├─ Figure 1: CPU time series
├─ Figure 2: Top CPU processes
├─ Figure 3: Memory time series
├─ Figure 4: Top memory processes
├─ Figure 5: Process state pie chart
├─ Figure 6: CPU by user
└─ Figure 7: Memory by user

generate_markdown_report(df, analyses)
└─ Creates full markdown report with embedded images
```

---

## Output Structure

### Report Sections

**1. Executive Summary**
- Monitoring period overview
- Key metrics at a glance
- Data volume

**2. CPU-Bound Slowdowns**
- What it means for users
- System CPU usage (peak, average)
- Top 10 CPU-consuming processes
- CPU distribution by user
- Impact assessment (🔴🟡🟢)

**3. Memory-Bound Slowdowns**
- What memory pressure means
- System memory usage (peak, average)
- Top 10 memory-consuming processes
- Memory distribution by user
- Paging risk assessment

**4. I/O-Bound Slowdowns**
- What I/O wait means
- Process state breakdown
- Processes waiting for disk (D state)
- I/O performance rating

**5. System Impact Summary**
- Primary bottleneck identification
- Combined impact assessment
- User-facing effect predictions

**6. Recommendations**
- Priority action items
- Specific processes to watch
- Advanced diagnostic commands
- Monitoring setup guidance

**7. Technical Notes**
- Methodology
- Metric definitions
- Process state codes

---

## Key Metrics Explained

### CPU Percentage
- **Definition:** Percentage of one CPU core
- **Example:** 100% = one core fully utilized
- **Multicore:** 400% = all four cores at 100%
- **Interpretation:** Higher = more CPU contention

### Memory Percentage
- **Definition:** Percentage of total system RAM
- **Example:** 50% = half of available RAM in use
- **Swapping:** >80% often causes disk paging
- **Interpretation:** Higher = more memory pressure

### RES (Resident Memory)
- **Definition:** Physical RAM currently allocated
- **Units:** Megabytes (MB)
- **Impact:** Direct measure of memory pressure

### VIRT (Virtual Memory)
- **Definition:** Total virtual address space
- **Includes:** Shared libraries, mapped files, swap
- **Note:** Doesn't directly indicate pressure

### Process States
| State | Meaning | Implication |
|-------|---------|------------|
| R | Running | Using CPU |
| S | Interruptible sleep | Waiting, responsive |
| D | Uninterruptible sleep | I/O wait (⚠️) |
| I | Idle | Not active |
| Z | Zombie | Dead but not cleaned |
| T | Stopped | Paused |

---

## Running the Script

### Basic Usage
```bash
cd /home/robbiec/Documents/Datasets/top_processes
.venv/bin/python3 generate_report.py
```

### Expected Output
```
======================================================================
SYSTEM PERFORMANCE ANALYSIS REPORT GENERATOR
======================================================================

📊 Loading data...
   ✓ Loaded 320,181 records from 1120 snapshots

🔍 Running analyses...
   • CPU-bound analysis... ✓
   • Memory-bound analysis... ✓
   • I/O-bound analysis... ✓
   • System impact analysis... ✓

📈 Creating visualizations...
✓ All visualizations generated successfully

📝 Generating markdown report...
   ✓ Report saved to: ...report_output/system_performance_report.md

======================================================================
REPORT SUMMARY
======================================================================

📊 Peak System CPU:     665.0%
📊 Average System CPU:  58.44%
🧠 Peak System Memory:  71.90%
🧠 Average Memory:      55.01%
⏳ I/O Wait Processes:  0.8%

📌 Top CPU Process:     (sd-parse-elf) (60.33% avg)
📌 Top Memory Process:  .opencode-wrapp (2.85% avg)

✅ Report generated successfully!
```

---

## Generated Visualizations

### Figure 1: CPU Time Series (141 KB)
- **Type:** Line chart
- **Shows:** CPU usage over 40-minute period
- **Includes:** Mean, max, ±1 std deviation
- **Interpretation:** Spikes = CPU-intensive periods

### Figure 2: Top CPU Processes (49 KB)
- **Type:** Horizontal bar chart
- **Shows:** Average CPU % for top 12 processes
- **Colors:** Red = high, green = low
- **Use:** Identify CPU hogs

### Figure 3: Memory Time Series (69 KB)
- **Type:** Line chart with fill
- **Shows:** Memory usage trends
- **Includes:** Mean, max, ±1 std deviation
- **Interpretation:** Persistent high memory = pressure

### Figure 4: Top Memory Processes (52 KB)
- **Type:** Horizontal bar chart
- **Shows:** Memory % for top 12 processes
- **Includes:** Resident memory in MB
- **Use:** Find memory-heavy applications

### Figure 5: Process State Distribution (39 KB)
- **Type:** Pie chart
- **Shows:** Percentage in each state (R/S/D/I/Z/T)
- **Key:** D state % indicates I/O wait
- **Interpretation:** High D% = disk bottleneck

### Figure 6: CPU by User (47 KB)
- **Type:** Horizontal bar chart
- **Shows:** Average CPU per user account
- **Use:** Identify problematic users
- **Context:** System vs. user processes

### Figure 7: Memory by User (47 KB)
- **Type:** Horizontal bar chart
- **Shows:** Average memory per user account
- **Use:** Find memory-hungry users
- **Context:** User applications vs. system

---

## Interpreting Results: Examples

### Example 1: High CPU
```
Peak CPU:        665%
Avg CPU:         58.44%
Top process:     (sd-parse-elf) at 60.33%
```
**Interpretation:**
- System has significant multi-threaded work
- ELF parsing (likely compilation) is happening
- 6.65 CPU cores worth of work happening at peak
- Users will experience lag during peaks

**Action:** Monitor compilation, schedule for off-hours

### Example 2: High Memory
```
Peak Memory:     71.90%
Avg Memory:      55.01%
Top process:     .opencode-wrapp at 2.85% (445 MB)
```
**Interpretation:**
- System is under moderate memory pressure
- 72% of RAM is allocated at peak
- Disk paging is likely occurring at peaks
- Users may experience occasional freezes

**Action:** Close unused applications, add RAM

### Example 3: I/O Wait
```
I/O Wait (D):    0.8%
Top processes:   kworker threads, ldconfig
```
**Interpretation:**
- Only 0.8% of processes waiting for I/O
- Disk is NOT the bottleneck
- CPU and memory are primary issues
- File operations should be responsive

**Action:** Focus on CPU/memory optimization

---

## Customization Guide

### Changing Data Source
```python
# Line 26-27 in script
DATA_PATH = Path(__file__).parent / "formatted_data" / "top_processes.parquet"
REPORT_PATH = OUTPUT_DIR / "system_performance_report.md"

# Modify to:
DATA_PATH = Path("/your/path/to/data.parquet")
REPORT_PATH = Path("/your/output/path/report.md")
```

### Adjusting Analysis Thresholds
```python
# Change percentile for outlier detection (line ~220)
high_cpu_threshold = df['CPU_PERCENT'].quantile(0.95)

# Modify to:
high_cpu_threshold = df['CPU_PERCENT'].quantile(0.90)  # Stricter
```

### Adding New Metrics
1. Create a new `analyze_*()` function
2. Add aggregation logic
3. Update `create_visualizations()` to include new plots
4. Update `generate_markdown_report()` to document findings

### Changing Impact Thresholds
```python
# Lines 855-875 in script control impact ratings
if analysis_cpu['cpu_by_user']['mean_cpu'].max() > 2.0:
    report.append("- 🔴 **HIGH IMPACT**")

# Modify > 2.0 threshold as needed
```

---

## Advanced Usage

### For Different Time Periods
The script works on any `top` output parquet file. Generate new datasets with:
```bash
# Capture process data for N seconds
while true; do top -bn1 >> top_output.txt; sleep 1; done

# Convert to parquet using provided scripts
python3 parse_top_processes.py top_output.txt
```

### For Different Thresholds
Edit percentile values:
```python
# Find high-usage outliers at stricter level
threshold = df['CPU_PERCENT'].quantile(0.99)  # Instead of 0.95
```

### For Specific User/Process Filtering
Add before analysis:
```python
# Filter to specific user
df = df[df['USER'] == 'robbiec']

# Or specific process
df = df[df['COMMAND'].str.contains('python')]
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'pandas'"
```bash
# Ensure using correct venv
.venv/bin/python3 -c "import pandas; print(pandas.__version__)"

# Or install missing packages
.venv/bin/pip install pandas numpy matplotlib pyarrow
```

### Issue: "FileNotFoundError: formatted_data/top_processes.parquet"
```bash
# Check file exists
ls -la /home/robbiec/Documents/Datasets/top_processes/formatted_data/

# Or modify path in script:
DATA_PATH = Path("/correct/path/to/data.parquet")
```

### Issue: "Permission denied" writing report
```bash
# Check output directory permissions
ls -la /home/robbiec/Documents/Datasets/top_processes/report_output/

# Or create it:
mkdir -p report_output
```

### Issue: Visualizations look poor
- Increase DPI: Change `dpi=100` to `dpi=200` in `create_visualizations()`
- Increase figure size: Change `figsize=(12, 8)` to `(14, 10)`

---

## Performance Optimization Tips

Based on typical results from your data:

### For CPU-Bound Issues
1. Monitor `(sd-parse-elf)` and compilation processes
2. Use `perf top` to profile hot functions
3. Schedule intensive builds during off-hours
4. Use `cgroups` or `cpulimit` to restrict CPU per process

### For Memory-Bound Issues
1. Monitor `.opencode-wrapp` and other large processes
2. Use `free -h && vmstat` to track memory
3. Set memory limits with `cgroups`
4. Consider increasing swap space
5. Add more RAM if budget allows

### For I/O-Bound Issues
1. Monitor with `iostat -x` and `iotop`
2. Check disk health: `smartctl` or `badblocks`
3. Consider SSD upgrade for performance
4. Use `noatime` mount option to reduce writes

---

## File Organization

```
/home/robbiec/Documents/Datasets/top_processes/
├── generate_report.py              # Main script (THIS FILE)
├── formatted_data/
│   └── top_processes.parquet      # Input data (320K records)
└── report_output/                  # Generated output directory
    ├── system_performance_report.md # Main report
    ├── README.md                    # Usage guide
    ├── fig_01_cpu_timeseries.png
    ├── fig_02_top_cpu_processes.png
    ├── fig_03_memory_timeseries.png
    ├── fig_04_top_memory_processes.png
    ├── fig_05_process_states.png
    ├── fig_06_cpu_by_user.png
    └── fig_07_memory_by_user.png
```

---

## Key Takeaways

✅ **Comprehensive Analysis:** Covers CPU, memory, and I/O bottlenecks

✅ **User-Focused:** Explains how each issue affects real users

✅ **Actionable:** Provides specific recommendations and commands

✅ **Professional Output:** Markdown + high-quality visualizations

✅ **Efficient:** Processes 320K records in seconds

✅ **Extensible:** Easy to customize and adapt

---

## Further Reading

- `report_output/README.md` - Detailed usage guide
- `report_output/system_performance_report.md` - Sample output
- Linux `ps` manual - Process state codes
- `man proc` - Process state documentation
- Brendan Gregg's performance resources - System tuning

---

**Generated:** 2026-04-16  
**Script Version:** 1.0  
**Status:** Production Ready ✓
