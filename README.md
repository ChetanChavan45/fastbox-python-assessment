# FastBox Mystery Delivery System

A Python solution for the FastBox coding assessment.
The system reads delivery data from JSON, assigns packages to the nearest agent,
simulates deliveries, and produces a structured performance report.

---

## Algorithm

### 1. Package Assignment
For each package:
- Find the package's warehouse coordinates.
- Calculate the **Euclidean distance** from every agent's **original start location** to that warehouse.
- Assign the package to the **nearest agent**.
- Tie-breaking: **lexicographically smaller agent ID** wins.

### 2. Delivery Simulation
Each agent delivers its assigned packages **in the order they appear in the input**.

The route for each agent:

```
current_position -> warehouse_1 -> destination_1 -> warehouse_2 -> destination_2 -> ...
```

**Route assumption:** After completing a delivery, an agent remains at the delivered
package's destination. The next delivery therefore starts from the agent's current
(updated) position. Assigned packages are processed in their original input order.

After each delivery the agent's **current position is updated** to that package's destination,
making subsequent legs start from that new location.

> **Note on sample numbers:** All calculations are performed from the coordinates supplied
> in the input file. The illustrative numbers printed in the PDF are examples only and may
> not match this implementation's output exactly.


### 3. Efficiency Formula

```
efficiency = total_distance / packages_delivered
```

- Lower efficiency value = better (shorter average distance per package).
- Agents with **zero packages** get `efficiency = 0.0` but are **excluded** from best-agent selection.

---

## Supported JSON Formats

### Format A – Dict (all test_case_*.json files)
```json
{
    "warehouses": { "W1": [x, y], "W2": [x, y] },
    "agents":     { "A1": [x, y] },
    "packages": [
        { "id": "P1", "warehouse": "W1", "destination": [x, y] }
    ]
}
```

### Format B – List (base_case.json)
```json
{
    "warehouses": [ {"id": "W1", "location": [x, y]} ],
    "agents":     [ {"id": "A1", "location": [x, y]} ],
    "packages": [
        { "id": "P1", "warehouse_id": "W1", "destination": [x, y] }
    ]
}
```

Both formats are automatically detected and normalised before processing.

---

## Project Structure

```
fastbox_delivery/
├── main.py               Entry point – CLI, orchestration, terminal output
├── delivery_system.py    Core logic (normalisation, assignment, simulation, report)
├── base_case.json        Provided base case (list format)
├── test_case_1.json      ...
├── test_case_10.json     ...
├── report.json           Generated output (created on run)
├── top_performer.csv     Best agent CSV export (bonus, created on run)
├── README.md
└── tests/
    └── test_delivery_system.py   Unit tests
```

---

## Requirements

- **Python 3.10+** (uses `X | Y` union type hints in function signatures)
- **No third-party packages** – standard library only (`math`, `json`, `csv`, `sys`, `os`, `unittest`)

---

## How to Run

```bash
# Run with a specific file
python main.py base_case.json
python main.py test_case_1.json

# Run without an argument (uses base_case.json by default)
python main.py
```

The output is written to `report.json` in the **current working directory**.
A bonus CSV `top_performer.csv` is also created.

---

## Example Command

```bash
cd fastbox_delivery
python main.py base_case.json
```

---

## How to Run Tests

```bash
# From the fastbox_delivery/ directory
python -m unittest discover tests -v

# Or with pytest (if installed)
python -m pytest tests/ -v
```

---

## Output Format

```json
{
    "A1": {
        "packages_delivered": 2,
        "total_distance": 85.32,
        "efficiency": 42.66
    },
    "A2": {
        "packages_delivered": 3,
        "total_distance": 120.45,
        "efficiency": 40.15
    },
    "best_agent": "A2"
}
```

---

## Assumptions

1. **Assignment uses original agent positions** – not updated positions during simulation.
2. **Package order matters** – deliveries are made in the same order as the input array.
3. **All coordinates are 2-D** – `[x, y]` only.
4. **Tie-breaking is lexicographic** – ensures deterministic output for any input.
5. **`best_agent` is `null`** if no packages exist or no agent delivered any package.
6. **Zero-package agents** appear in the report with `packages_delivered: 0`, `total_distance: 0.0`, `efficiency: 0.0`.
7. **Both `"warehouse"` and `"warehouse_id"` keys** are accepted in packages; `"warehouse"` takes precedence.

---

## Bonus Features

| Feature | File |
|---------|------|
| ASCII route summary | Printed to terminal after each run |
| Best performer CSV export | `top_performer.csv` |
