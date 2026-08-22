import argparse
import csv
import json
import math
import statistics
from datetime import datetime
from pathlib import Path


METRICS = (
    "app_cpu_percent",
    "app_memory_mib",
    "app_pids",
    "db_cpu_percent",
    "db_memory_mib",
    "db_pids",
    "containers_cpu_percent_total",
    "containers_memory_mib_total",
    "containers_pids_total",
    "vm_cpu_percent",
    "vm_working_set_mib",
    "vm_private_mib",
)


def parse_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_measurements(path, expected_scenario):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"scenario", "sample", "timestamp_utc", *METRICS}
        missing_columns = required - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(
                f"{path} is missing columns: {sorted(missing_columns)}"
            )
        raw_rows = list(reader)

    if len(raw_rows) < 2:
        raise ValueError(f"{path} must contain at least two samples")

    rows = []
    for raw in raw_rows:
        if raw["scenario"] != expected_scenario:
            raise ValueError(
                f"{path} contains scenario {raw['scenario']!r}, "
                f"expected {expected_scenario!r}"
            )

        row = {
            "scenario": raw["scenario"],
            "sample": int(raw["sample"]),
            "timestamp_utc": parse_timestamp(raw["timestamp_utc"]),
        }
        for metric in METRICS:
            value = float(raw[metric])
            if not math.isfinite(value) or value < 0:
                raise ValueError(
                    f"{path} has invalid {metric} value: {raw[metric]!r}"
                )
            row[metric] = value
        rows.append(row)

    expected_samples = list(range(1, len(rows) + 1))
    actual_samples = [row["sample"] for row in rows]
    if actual_samples != expected_samples:
        raise ValueError(
            f"{path} sample sequence is {actual_samples}, "
            f"expected {expected_samples}"
        )

    timestamps = [row["timestamp_utc"] for row in rows]
    if any(current <= previous for previous, current in zip(
        timestamps,
        timestamps[1:],
    )):
        raise ValueError(f"{path} timestamps are not strictly increasing")

    return rows


def nearest_rank(values, percentile):
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile / 100) * len(ordered)))
    return ordered[rank - 1]


def summarize_metric(rows, metric):
    values = [row[metric] for row in rows]
    return {
        "mean": round(statistics.fmean(values), 3),
        "median": round(statistics.median(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "p95_nearest_rank": round(nearest_rank(values, 95), 3),
    }


def ratio(numerator, denominator):
    if denominator == 0:
        return None
    return round(numerator / denominator, 3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--idle", required=True, type=Path)
    parser.add_argument("--load", required=True, type=Path)
    parser.add_argument("--http", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    idle = read_measurements(args.idle, "idle")
    load = read_measurements(args.load, "load")
    with args.http.open(encoding="utf-8") as stream:
        http_result = json.load(stream)

    if http_result["failed_requests"] != 0:
        raise ValueError("HTTP load result contains failed requests")
    if http_result["successful_requests"] != http_result["total_requests"]:
        raise ValueError("HTTP success count does not equal total requests")

    idle_summary = {
        metric: summarize_metric(idle, metric) for metric in METRICS
    }
    load_summary = {
        metric: summarize_metric(load, metric) for metric in METRICS
    }

    idle_container_memory = idle_summary[
        "containers_memory_mib_total"
    ]["mean"]
    load_container_memory = load_summary[
        "containers_memory_mib_total"
    ]["mean"]
    idle_vm_memory = idle_summary["vm_working_set_mib"]["mean"]
    load_vm_memory = load_summary["vm_working_set_mib"]["mean"]
    load_app_cpu = load_summary["app_cpu_percent"]["mean"]
    load_total_cpu = load_summary[
        "containers_cpu_percent_total"
    ]["mean"]

    result = {
        "quality_checks": {
            "idle_rows": len(idle),
            "load_rows": len(load),
            "idle_scenario_valid": True,
            "load_scenario_valid": True,
            "sample_sequences_valid": True,
            "timestamps_strictly_increasing": True,
            "numeric_values_finite_and_nonnegative": True,
            "http_failures": http_result["failed_requests"],
        },
        "idle": idle_summary,
        "load": load_summary,
        "http_load": http_result,
        "comparisons": {
            "container_cpu_mean_load_to_idle_ratio": ratio(
                load_summary["containers_cpu_percent_total"]["mean"],
                idle_summary["containers_cpu_percent_total"]["mean"],
            ),
            "vm_cpu_mean_load_to_idle_ratio": ratio(
                load_summary["vm_cpu_percent"]["mean"],
                idle_summary["vm_cpu_percent"]["mean"],
            ),
            "container_memory_mean_load_minus_idle_mib": round(
                load_container_memory - idle_container_memory,
                3,
            ),
            "vm_working_set_mean_load_minus_idle_mib": round(
                load_vm_memory - idle_vm_memory,
                3,
            ),
            "vm_to_container_memory_mean_ratio_idle": ratio(
                idle_vm_memory,
                idle_container_memory,
            ),
            "vm_to_container_memory_mean_ratio_load": ratio(
                load_vm_memory,
                load_container_memory,
            ),
            "app_share_of_container_load_cpu_mean": ratio(
                load_app_cpu,
                load_total_cpu,
            ),
        },
        "methodology": {
            "container_cpu": (
                "delta(CPUNano) / delta(SystemNano) * 100; "
                "100 percent equals one fully utilized CPU core"
            ),
            "container_memory": "Podman cgroup usage, app plus DB",
            "vm_cpu_and_memory": (
                "Windows Win32_PerfFormattedData_PerfProc_Process "
                "for vmmemWSL"
            ),
            "p95": "nearest-rank percentile",
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(f"summary={args.output.resolve()}")


if __name__ == "__main__":
    main()
