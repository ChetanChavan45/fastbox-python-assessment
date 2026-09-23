"""
FastBox Mystery Delivery System - entry point.

Usage:
    python main.py <input.json>           Run with a specific input file
    python main.py                        Runs with default: base_case.json

On success:
    - Prints a concise summary to the terminal (including ASCII route)
    - Writes the complete report to report.json
    - Exports the best performer to top_performer.csv (bonus)
"""

import csv
import sys
import os

from delivery_system import (
    load_json,
    normalise_input,
    assign_packages,
    simulate_deliveries,
    generate_report,
    save_report,
    validate_delivery_completeness,
)

# Default input file (used when no argument is provided)
DEFAULT_INPUT = "base_case.json"
OUTPUT_JSON = "report.json"
OUTPUT_CSV = "top_performer.csv"


# ---------------------------------------------------------------------------
# ASCII route summary (bonus)
# ---------------------------------------------------------------------------

def print_ascii_routes(agent_queues: dict, agent_starts: dict) -> None:
    """Print a compact route summary for every agent."""
    print("\n-- Route Summary -----------------------------------------------")
    for agent_id, pkg_list in sorted(agent_queues.items()):
        sx, sy = agent_starts[agent_id]
        steps = [f"START({sx:.0f},{sy:.0f})"]
        for pkg in pkg_list:
            steps.append(pkg["warehouse"])
            steps.append(pkg["id"])
        print(f"  {agent_id}: {' -> '.join(steps)}")
    print("---------------------------------------------------------------")


# ---------------------------------------------------------------------------
# CSV export (bonus)
# ---------------------------------------------------------------------------

def export_top_performer(report: dict, output_path: str = OUTPUT_CSV) -> None:
    """Write the best agent's stats to a CSV file."""
    best = report.get("best_agent")
    if best is None:
        return  # nothing to export

    row = report[best]
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["agent_id", "packages_delivered", "total_distance", "efficiency"],
            )
            writer.writeheader()
            writer.writerow({
                "agent_id": best,
                "packages_delivered": row["packages_delivered"],
                "total_distance": row["total_distance"],
                "efficiency": row["efficiency"],
            })
        print(f"  Top performer exported: {output_path}")
    except OSError as exc:
        print(f"  [WARNING] Could not write CSV: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Resolve input file path
    if len(sys.argv) == 2:
        input_path = sys.argv[1]
    elif len(sys.argv) == 1:
        # Try the default file in the same directory as main.py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        input_path = os.path.join(script_dir, DEFAULT_INPUT)
        if not os.path.exists(input_path):
            print(
                "Usage: python main.py <input.json>\n"
                f"       (No argument given and default '{DEFAULT_INPUT}' not found.)"
            )
            sys.exit(1)
    else:
        print("Usage: python main.py <input.json>")
        sys.exit(1)

    print(f"\n{'='*55}")
    print(f"  FastBox Mystery Delivery System")
    print(f"  Input: {input_path}")
    print(f"{'='*55}")

    # Step 1: Load
    raw_data = load_json(input_path)

    # Step 2: Normalise (handles both JSON formats)
    warehouses, agents, packages = normalise_input(raw_data)

    print(f"  Warehouses : {len(warehouses)}")
    print(f"  Agents     : {len(agents)}")
    print(f"  Packages   : {len(packages)}")

    if not packages:
        print("\n  [INFO] No packages to deliver. Generating empty report.")
        # Build zero-stats report for all agents
        results = {a: {"packages_delivered": 0, "total_distance": 0.0, "route": []} for a in agents}
        report = generate_report(results)
        save_report(report, OUTPUT_JSON)
        print(f"\n  Report saved: {OUTPUT_JSON}")
        return

    # Step 3: Assign packages
    agent_queues = assign_packages(packages, warehouses, agents)

    # Step 4: Simulate deliveries
    results = simulate_deliveries(agent_queues, warehouses, agents)

    # Step 5: Integrity check
    validate_delivery_completeness(packages, results)

    # Step 6: Generate report
    report = generate_report(results)

    # Step 7: Save report
    save_report(report, OUTPUT_JSON)

    # -- Terminal summary ----------------------------------------------------
    print("\n-- Delivery Report ---------------------------------------------")
    for agent_id in sorted(report.keys()):
        if agent_id == "best_agent":
            continue
        data = report[agent_id]
        print(
            f"  {agent_id}: {data['packages_delivered']:>3} pkg(s) | "
            f"distance={data['total_distance']:>9.2f} | "
            f"efficiency={data['efficiency']:>9.2f}"
        )

    print(f"\n  Best agent: {report['best_agent']}")
    print(f"  Report saved: {OUTPUT_JSON}")

    # -- Bonus: ASCII routes -------------------------------------------------
    print_ascii_routes(agent_queues, agents)

    # -- Bonus: CSV export ---------------------------------------------------
    export_top_performer(report, OUTPUT_CSV)

    print()


if __name__ == "__main__":
    main()
