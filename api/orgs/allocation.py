from dataclasses import dataclass
from typing import Dict, List

# Intentionally avoid importing models here to keep this module pure for unit tests


@dataclass
class AllocationResult:
    total: int
    fixed: Dict[int, int]
    proportional: Dict[int, int]


def compute_enterprise_allocations(total_monthly: int, org_ids: List[int], fixed_map: Dict[int, int]) -> AllocationResult:
    """Given total proposals per month and fixed allocations for some orgs, distribute remainder equally among
    the zero-allocation orgs. Returns per-org allocations.
    """
    fixed = {oid: max(0, int(fixed_map.get(oid, 0) or 0)) for oid in org_ids}
    sum_fixed = sum(fixed.values())
    remaining = max(0, total_monthly - sum_fixed)
    zeros = [oid for oid in org_ids if fixed.get(oid, 0) == 0]
    proportional: Dict[int, int] = {}
    if zeros:
        base = remaining // len(zeros)
        extra = remaining % len(zeros)
        for idx, oid in enumerate(zeros):
            proportional[oid] = base + (1 if idx < extra else 0)
    return AllocationResult(total=total_monthly, fixed=fixed, proportional=proportional)
