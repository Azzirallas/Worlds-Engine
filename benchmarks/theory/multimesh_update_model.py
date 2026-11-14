"""CPU-only workload model for public Godot MultiMesh dirty-region uploads.

This models byte counts and control thresholds, NOT GPU timing or driver costs.
No Unreal source or implementation details are used.
"""

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class Policy:
    """Specify observed Godot region/threshold policy and workload dimensions."""
    instances: int
    visible: int
    region_size: int = 512
    threshold: int = 32
    bytes_per_instance: int = 48

    def __post_init__(self):
        """Reject nonsensical input rather than producing credible-looking estimates."""
        if (self.instances < 0 or not 0 <= self.visible <= self.instances
                or self.region_size <= 0 or self.threshold < 0
                or self.bytes_per_instance <= 0):
            raise ValueError("Invalid MultiMesh model dimensions")

    @property
    def visible_regions(self):
        """Count region slots actually included in the drawn instance prefix."""
        return ceil(self.visible / self.region_size)


def expected_dirty_regions(instances, region_size, change_probability):
    """Compute exact expectation for independently changing instances."""
    if instances < 0 or region_size <= 0 or not 0 <= change_probability <= 1:
        raise ValueError("Invalid occupancy model arguments")
    return sum(1 - (1 - change_probability) ** min(region_size, instances - start)
               for start in range(0, instances, region_size))


def estimate_upload(policy, current_changes, previous_changes=()):
    """Estimate policy-selected bytes for changed instance indices.

    Current and previous region counts are added, as observed in the source.
    Overlapping regions may therefore count twice for the full-upload switch.
    """
    changes = (set(current_changes), set(previous_changes))
    if any(index < 0 or index >= policy.instances for batch in changes for index in batch):
        raise ValueError("Changed index outside instance range")
    current, previous = ({i // policy.region_size for i in batch} for batch in changes)
    total_dirty = len(current) + len(previous)
    if total_dirty == 0:
        return {"mode": "none", "bytes": 0, "dirty_regions": 0}

    full = total_dirty > policy.threshold or total_dirty > policy.visible_regions / 2
    if full:
        estimate = policy.visible * policy.bytes_per_instance
    else:
        estimate = sum(min(policy.region_size, policy.visible - region * policy.region_size)
                       * policy.bytes_per_instance for region in current | previous
                       if region < policy.visible_regions)
    return {"mode": "full" if full else "regions", "bytes": estimate,
            "dirty_regions": total_dirty}


def main():
    """Print reproducible theoretical cases, explicitly not frame benchmarks."""
    policy = Policy(instances=100_000, visible=100_000)
    print("THEORETICAL MODEL ONLY — no GPU execution or measured performance")
    print("N=100000, 512-instance regions, 48-byte example transform, fully visible")
    for p in (0.0001, 0.0005, 0.001, 0.01):
        print(f"change probability={p:.4%} expected dirty regions="
              f"{expected_dirty_regions(policy.instances, policy.region_size, p):.2f}")
    cases = (("100 clustered edits", range(100)),
             ("100 scattered edits", range(0, 100_000, 1000)))
    for label, indices in cases:
        result = estimate_upload(policy, indices)
        print(f"{label}: {result['mode']}; modeled upload bytes={result['bytes']:,}")


if __name__ == "__main__":
    main()
