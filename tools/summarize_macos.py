"""Summarize CatMate's three macOS residency measurements as JSON."""
import argparse
import json
from pathlib import Path
import re
import statistics


def mib(value):
    match = re.fullmatch(r"([\d.]+)([BKMG]?)[+-]?", value)
    if not match:
        raise ValueError(f"Unrecognized top memory value: {value}")
    return float(match[1]) * {"": 1, "B": 1, "K": 1024,
                              "M": 1024**2, "G": 1024**3}[match[2]] / 1024**2


def summarize(folder, phase):
    # The first top snapshot has no previous observation for interval counters.
    samples = (folder / f"{phase}.top").read_text().split("Processes:")[2:]
    system_busy = []
    processes = []
    for sample in samples:
        idle = re.search(r"([\d.]+)% idle", sample)
        system_busy.append(100 - float(idle[1]))
        if phase != "baseline":
            rows = sample.partition("IDLEW")[2].strip().splitlines()
            if rows:
                _, cpu, memory, power, _ = rows[0].split()
                processes.append((float(cpu), mib(memory), float(power)))
    if len(system_busy) < 60:
        raise ValueError(f"Incomplete top capture for {phase}: {len(samples)} intervals")
    result = {"top_intervals": len(system_busy), "system_busy_percent": statistics.mean(system_busy)}
    if phase == "baseline":
        return result
    if len(processes) < 59:
        raise ValueError(f"Incomplete process capture for {phase}: {len(processes)} intervals")
    cpu, memory, power = zip(*processes)
    usage = json.loads((folder / f"{phase}-usage.json").read_text())
    first, last = usage[0], usage[-1]
    duration = last["monotonic_s"] - first["monotonic_s"]
    if duration < 590:
        raise ValueError(f"Incomplete rusage capture for {phase}: {duration} seconds")
    result.update({
        "process_intervals": len(cpu), "process_cpu_percent": statistics.mean(cpu),
        "average_footprint_mib": statistics.mean(memory), "top_power": statistics.mean(power),
        "rusage_seconds": duration, "rss_first_mib": first["rss_bytes"] / 1024**2,
        "rss_last_mib": last["rss_bytes"] / 1024**2,
        "interrupt_wakeups_per_s": (last["interrupt_wakeups"] - first["interrupt_wakeups"]) / duration,
        "package_wakeups_per_s": (last["package_wakeups"] - first["package_wakeups"]) / duration,
        "process_energy_mw": (last["energy_nj"] - first["energy_nj"]) / duration / 1e6,
        "animation": json.loads((folder / f"{phase}.json").read_text())
    })
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps({p: summarize(args.folder, p) for p in ("baseline", "idle", "walk")}, indent=2))
