"""
FastBox Mystery Delivery System - core logic.

Supports two JSON input formats:
  - Dict format  (test_case_*.json): warehouses/agents are dicts  {"ID": [x, y]}
  - List format  (base_case.json):   warehouses/agents are lists  [{"id": "W1", "location": [x, y]}]

Package field 'warehouse' and 'warehouse_id' are both accepted.
"""

import json
import math
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Types (simple dicts - no heavy dataclasses needed for this scale)
# ---------------------------------------------------------------------------
# Normalised internal format:
#   warehouses : dict[str, list[float]]   {"W1": [x, y], ...}
#   agents     : dict[str, list[float]]   {"A1": [x, y], ...}
#   packages   : list[dict]               [{"id": "P1", "warehouse": "W1", "destination": [x, y]}, ...]


# ---------------------------------------------------------------------------
# 1. I/O helpers
# ---------------------------------------------------------------------------

def load_json(filepath: str) -> dict:
    """Load and parse a JSON file; raise a clear error on failure."""
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        sys.exit(f"[ERROR] File not found: {filepath}")
    except json.JSONDecodeError as exc:
        sys.exit(f"[ERROR] Malformed JSON in '{filepath}': {exc}")


# ---------------------------------------------------------------------------
# 2. Normalisation
# ---------------------------------------------------------------------------

def _normalise_location_dict(raw: dict | list, label: str) -> dict[str, list[float]]:
    """
    Convert either input format for warehouses/agents into a uniform dict.

    Dict format  -> {"W1": [34, 29], ...}   (already done - just validate)
    List format  -> [{"id": "W1", "location": [34, 29]}, ...]  -> same dict
    """
    if isinstance(raw, dict):
        result: dict[str, list[float]] = {}
        for key, value in raw.items():
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                sys.exit(f"[ERROR] {label} '{key}' must have exactly 2 coordinates, got: {value}")
            result[key] = [float(value[0]), float(value[1])]
        return result

    if isinstance(raw, list):
        result = {}
        for item in raw:
            if not isinstance(item, dict):
                sys.exit(f"[ERROR] Each {label} entry must be a JSON object, got: {item}")
            item_id = item.get("id")
            location = item.get("location")
            if item_id is None:
                sys.exit(f"[ERROR] A {label} entry is missing the 'id' field: {item}")
            if not isinstance(location, (list, tuple)) or len(location) != 2:
                sys.exit(f"[ERROR] {label} '{item_id}' must have a 'location' of 2 coordinates.")
            result[str(item_id)] = [float(location[0]), float(location[1])]
        return result

    sys.exit(f"[ERROR] '{label}' must be a JSON object or array, got: {type(raw).__name__}")


def _normalise_packages(raw: list) -> list[dict]:
    """
    Return packages in the uniform format.
    Accepts both 'warehouse' and 'warehouse_id' as the field name.
    """
    if not isinstance(raw, list):
        sys.exit("[ERROR] 'packages' must be a JSON array.")

    normalised = []
    for pkg in raw:
        if not isinstance(pkg, dict):
            sys.exit(f"[ERROR] Each package must be a JSON object, got: {pkg}")

        pkg_id = pkg.get("id")
        if pkg_id is None:
            sys.exit(f"[ERROR] A package is missing the 'id' field: {pkg}")

        # Accept both field names; 'warehouse' takes precedence over 'warehouse_id'
        warehouse_id = pkg.get("warehouse")
        if warehouse_id is None:
            warehouse_id = pkg.get("warehouse_id")
        if warehouse_id is None:
            sys.exit(f"[ERROR] Package '{pkg_id}' has no 'warehouse' or 'warehouse_id' field.")

        destination = pkg.get("destination")
        if not isinstance(destination, (list, tuple)) or len(destination) != 2:
            sys.exit(f"[ERROR] Package '{pkg_id}' must have a 'destination' of 2 coordinates.")

        try:
            dest = [float(destination[0]), float(destination[1])]
        except (TypeError, ValueError):
            sys.exit(f"[ERROR] Package '{pkg_id}' destination contains non-numeric values.")

        normalised.append({
            "id": str(pkg_id),
            "warehouse": str(warehouse_id),
            "destination": dest,
        })
    return normalised


def normalise_input(raw_data: dict) -> tuple[dict, dict, list]:
    """
    Parse raw JSON dict into three normalised structures:
      (warehouses, agents, packages)
    Works for both supported input formats.
    """
    if not isinstance(raw_data, dict):
        sys.exit("[ERROR] Top-level JSON must be an object.")

    raw_warehouses = raw_data.get("warehouses")
    raw_agents = raw_data.get("agents")
    raw_packages = raw_data.get("packages", [])

    if raw_warehouses is None:
        sys.exit("[ERROR] Input is missing required key 'warehouses'.")
    if raw_agents is None:
        sys.exit("[ERROR] Input is missing required key 'agents'.")

    warehouses = _normalise_location_dict(raw_warehouses, "warehouse")
    agents = _normalise_location_dict(raw_agents, "agent")
    packages = _normalise_packages(raw_packages)

    if not warehouses:
        sys.exit("[ERROR] No warehouses found in input.")
    if not agents:
        sys.exit("[ERROR] No agents found in input.")

    # Validate every package references a known warehouse
    for pkg in packages:
        if pkg["warehouse"] not in warehouses:
            sys.exit(
                f"[ERROR] Package '{pkg['id']}' references unknown warehouse '{pkg['warehouse']}'."
                f" Known warehouses: {list(warehouses.keys())}"
            )

    return warehouses, agents, packages


# ---------------------------------------------------------------------------
# 3. Core algorithm helpers
# ---------------------------------------------------------------------------

def euclidean_distance(point_a: list[float], point_b: list[float]) -> float:
    """Return the Euclidean distance between two 2-D points."""
    return math.sqrt((point_b[0] - point_a[0]) ** 2 + (point_b[1] - point_a[1]) ** 2)


def assign_packages(
    packages: list[dict],
    warehouses: dict[str, list[float]],
    agents: dict[str, list[float]],
) -> dict[str, list[dict]]:
    """
    Assign every package to the nearest agent.

    Assignment criterion: distance from agent's ORIGINAL start location
    to the package's warehouse (NOT the destination).

    Tie-breaking: lexicographically smaller agent ID wins.

    Returns a dict mapping agent_id -> ordered list of packages
    (in the same relative order they appear in the input).
    """
    # Initialise empty queues for every agent so idle agents still appear in the report
    agent_queues: dict[str, list[dict]] = {agent_id: [] for agent_id in agents}

    for pkg in packages:
        warehouse_loc = warehouses[pkg["warehouse"]]

        # Find the nearest agent (stable tie-break: lexicographic agent ID)
        best_agent: Optional[str] = None
        best_dist = float("inf")

        for agent_id in sorted(agents.keys()):          # sort ensures deterministic tie-break
            dist = euclidean_distance(agents[agent_id], warehouse_loc)
            if dist < best_dist:
                best_dist = dist
                best_agent = agent_id

        agent_queues[best_agent].append(pkg)

    return agent_queues


# ---------------------------------------------------------------------------
# 4. Delivery simulation
# ---------------------------------------------------------------------------

def simulate_deliveries(
    agent_queues: dict[str, list[dict]],
    warehouses: dict[str, list[float]],
    agents: dict[str, list[float]],
) -> dict[str, dict]:
    """
    Simulate deliveries and compute per-agent statistics.

    Route for each agent:
      current_pos -> warehouse_1 -> dest_1 -> warehouse_2 -> dest_2 -> ...

    After each delivery, the agent's current position becomes that package's destination.
    Full floating-point precision is maintained throughout.

    Returns a dict:
      {agent_id: {"packages_delivered": int, "total_distance": float, "route": [str, ...]}}
    """
    results: dict[str, dict] = {}

    for agent_id, pkg_list in agent_queues.items():
        current_pos = list(agents[agent_id])  # copy - do not mutate the original
        total_dist = 0.0
        route = [f"START({current_pos[0]:.0f},{current_pos[1]:.0f})"]

        for pkg in pkg_list:
            warehouse_loc = warehouses[pkg["warehouse"]]
            dest = pkg["destination"]

            # Leg 1: current position -> warehouse
            leg1 = euclidean_distance(current_pos, warehouse_loc)
            # Leg 2: warehouse -> destination
            leg2 = euclidean_distance(warehouse_loc, dest)

            total_dist += leg1 + leg2
            route.append(f"{pkg['warehouse']}")
            route.append(f"{pkg['id']}")

            # Update agent's position to this delivery's destination
            current_pos = list(dest)

        results[agent_id] = {
            "packages_delivered": len(pkg_list),
            "total_distance": total_dist,
            "route": route,
        }

    return results


# ---------------------------------------------------------------------------
# 5. Report generation
# ---------------------------------------------------------------------------

def calculate_best_agent(results: dict[str, dict]) -> Optional[str]:
    """
    Return the agent ID with the lowest efficiency (distance per package)
    among agents that delivered at least one package.
    Returns None if no agent delivered any package.
    """
    best_agent: Optional[str] = None
    best_efficiency = float("inf")

    for agent_id, data in results.items():
        if data["packages_delivered"] == 0:
            continue
        eff = data["total_distance"] / data["packages_delivered"]
        # Tie-break: lexicographically smaller agent ID
        if eff < best_efficiency or (eff == best_efficiency and (best_agent is None or agent_id < best_agent)):
            best_efficiency = eff
            best_agent = agent_id

    return best_agent


def generate_report(results: dict[str, dict]) -> dict:
    """
    Build the final report dict with rounded values.
    efficiency = total_distance / packages_delivered  (0.0 for idle agents).
    """
    report: dict = {}

    for agent_id, data in results.items():
        delivered = data["packages_delivered"]
        total_dist = data["total_distance"]

        if delivered > 0:
            efficiency = total_dist / delivered
        else:
            efficiency = 0.0

        report[agent_id] = {
            "packages_delivered": delivered,
            "total_distance": round(total_dist, 2),
            "efficiency": round(efficiency, 2),
        }

    report["best_agent"] = calculate_best_agent(results)
    return report


def save_report(report: dict, output_path: str = "report.json") -> None:
    """Write the report to a JSON file with 4-space indentation."""
    try:
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=4)
    except OSError as exc:
        sys.exit(f"[ERROR] Could not write report to '{output_path}': {exc}")


# ---------------------------------------------------------------------------
# 6. Validation
# ---------------------------------------------------------------------------

def validate_delivery_completeness(
    packages: list[dict],
    results: dict[str, dict],
) -> None:
    """
    Verify every package was delivered exactly once.
    Raises RuntimeError with a clear message if the invariant is violated.
    """
    total_delivered = sum(d["packages_delivered"] for d in results.values())
    expected = len(packages)
    if total_delivered != expected:
        raise RuntimeError(
            f"[INTEGRITY ERROR] Expected {expected} packages delivered, "
            f"but got {total_delivered}. Check assignment logic."
        )
