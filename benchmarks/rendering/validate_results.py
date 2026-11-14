#!/usr/bin/env python3
"""Validate Worlds Engine rendering benchmark CSVs without external dependencies."""

import argparse
import csv
import math
from pathlib import Path


SUMMARY_COLUMNS = ("mode", "count", "sample_frames", "frame_p50_ms", "frame_p95_ms", "frame_p99_ms", "render_cpu_p50_ms", "render_cpu_p95_ms", "render_gpu_p50_ms", "render_gpu_p95_ms", "valid_gpu_samples")
SAMPLE_COLUMNS = ("frame", "frame_delta_ms", "render_cpu_ms", "render_gpu_ms", "draw_calls", "objects")


def load_csv(path: Path):
    """Read a CSV with header validation and no empty data records."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"{path}: missing or duplicate CSV headers")
        rows = list(reader)
    if not rows or any(None in row or any(value is None or value == "" for value in row.values()) for row in rows):
        raise ValueError(f"{path}: empty, incomplete or malformed CSV records")
    return set(reader.fieldnames), rows


def finite_number(row, field, *, minimum=None):
    """Validate a reported numeric field, rejecting nonfinite data."""
    value = float(row[field])
    if not math.isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(f"{field}: invalid numeric value {row[field]!r}")
    return value


def percentile(values, fraction):
    """Match the benchmark's nearest-rank-on-index percentile convention."""
    if not values:
        return -1.0
    ordered = sorted(values)
    return ordered[math.ceil((len(ordered) - 1) * fraction)]


def validate(summary_path: Path, samples_path=None):
    """Check sample counts, metrics, unavailability markers, and summary consistency."""
    if samples_path is None:
        samples_path = summary_path.with_name(summary_path.stem + "_samples.csv")
    fields, summary_rows = load_csv(summary_path)
    missing = set(SUMMARY_COLUMNS) - fields
    if missing or len(summary_rows) != 1:
        raise ValueError(f"{summary_path}: expected one summary row; missing {sorted(missing)}")
    sample_fields, samples = load_csv(samples_path)
    missing = set(SAMPLE_COLUMNS) - sample_fields
    if missing:
        raise ValueError(f"{samples_path}: missing columns {sorted(missing)}")
    summary = summary_rows[0]
    expected_count = int(summary["sample_frames"])
    if expected_count <= 0 or expected_count != len(samples):
        raise ValueError(f"sample count mismatch: expected {expected_count}, found {len(samples)}")
    if int(summary["count"]) < 0:
        raise ValueError("object count cannot be negative")

    intervals, cpu, gpu = [], [], []
    for index, sample in enumerate(samples):
        if int(sample["frame"]) != index:
            raise ValueError(f"unexpected frame index at sample {index}")
        intervals.append(finite_number(sample, "frame_delta_ms", minimum=0))
        cpu.append(finite_number(sample, "render_cpu_ms", minimum=0))
        gpu.append(finite_number(sample, "render_gpu_ms", minimum=-1))
        finite_number(sample, "draw_calls", minimum=0)
        finite_number(sample, "objects", minimum=0)
    # Zero render timings from the engine are explicitly treated as unavailable.
    cpu_valid = [value for value in cpu if value > 0]
    gpu_valid = [value for value in gpu if value > 0]
    if len(gpu_valid) != int(summary["valid_gpu_samples"]):
        raise ValueError("GPU valid-sample counter mismatch")
    expectations = {
        "frame_p50_ms": percentile(intervals, .50),
        "frame_p95_ms": percentile(intervals, .95),
        "frame_p99_ms": percentile(intervals, .99),
        "render_cpu_p50_ms": percentile(cpu_valid, .50),
        "render_cpu_p95_ms": percentile(cpu_valid, .95),
        "render_gpu_p50_ms": percentile(gpu_valid, .50),
        "render_gpu_p95_ms": percentile(gpu_valid, .95),
    }
    for key, expected in expectations.items():
        measured = finite_number(summary, key)
        if not math.isclose(measured, expected, abs_tol=.002, rel_tol=0):
            raise ValueError(f"{key}: reported {measured} but samples yield {expected:.6f}")
    return summary, len(samples), len(gpu_valid)


def main():
    """Validate one or more runs and print their individually verified metrics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summaries", nargs="+", type=Path, help="Summary CSV paths; raw files are found beside each summary")
    args = parser.parse_args()
    failed = False
    for path in args.summaries:
        try:
            summary, frames, gpu_count = validate(path)
            gpu = f"{float(summary['render_gpu_p95_ms']):.3f} ms" if gpu_count else "unavailable"
            print(f"PASS {path}: {summary['mode']} count={summary['count']} "
                  f"samples={frames} frame_p95={summary['frame_p95_ms']} ms gpu_p95={gpu}")
        except (OSError, ValueError, KeyError) as error:
            failed = True
            print(f"FAIL {path}: {error}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
