"""
Unit tests for FastBox Delivery System core logic.

Run with:  python -m pytest tests/ -v
       or: python -m unittest discover tests
"""

import math
import unittest
import sys
import os

# Allow import from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from delivery_system import (
    euclidean_distance,
    normalise_input,
    assign_packages,
    simulate_deliveries,
    generate_report,
    calculate_best_agent,
    validate_delivery_completeness,
)


class TestEuclideanDistance(unittest.TestCase):
    """Test the distance calculation function."""

    def test_basic_345_triangle(self):
        """Classic 3-4-5 right triangle."""
        self.assertAlmostEqual(euclidean_distance([0, 0], [3, 4]), 5.0)

    def test_same_point_is_zero(self):
        self.assertAlmostEqual(euclidean_distance([10, 20], [10, 20]), 0.0)

    def test_horizontal_line(self):
        self.assertAlmostEqual(euclidean_distance([0, 5], [10, 5]), 10.0)

    def test_vertical_line(self):
        self.assertAlmostEqual(euclidean_distance([3, 0], [3, 7]), 7.0)

    def test_float_coordinates(self):
        result = euclidean_distance([1.5, 2.5], [4.5, 6.5])
        expected = math.sqrt(9 + 16)  # sqrt(25) = 5
        self.assertAlmostEqual(result, expected)


class TestNormaliseInput(unittest.TestCase):
    """Test that both JSON formats produce the same internal structure."""

    def _dict_format(self):
        return {
            "warehouses": {"W1": [10, 20], "W2": [30, 40]},
            "agents": {"A1": [5, 5]},
            "packages": [{"id": "P1", "warehouse": "W1", "destination": [15, 25]}],
        }

    def _list_format(self):
        return {
            "warehouses": [
                {"id": "W1", "location": [10, 20]},
                {"id": "W2", "location": [30, 40]},
            ],
            "agents": [{"id": "A1", "location": [5, 5]}],
            "packages": [{"id": "P1", "warehouse_id": "W1", "destination": [15, 25]}],
        }

    def test_dict_format_normalises(self):
        wh, ag, pkgs = normalise_input(self._dict_format())
        self.assertEqual(wh, {"W1": [10.0, 20.0], "W2": [30.0, 40.0]})
        self.assertEqual(ag, {"A1": [5.0, 5.0]})
        self.assertEqual(len(pkgs), 1)
        self.assertEqual(pkgs[0]["warehouse"], "W1")

    def test_list_format_normalises(self):
        """base_case.json style: list of objects + 'warehouse_id' in packages."""
        wh, ag, pkgs = normalise_input(self._list_format())
        self.assertEqual(wh["W1"], [10.0, 20.0])
        self.assertEqual(ag["A1"], [5.0, 5.0])
        self.assertEqual(pkgs[0]["warehouse"], "W1")   # normalised from 'warehouse_id'

    def test_both_formats_produce_same_result(self):
        wh_d, ag_d, pkgs_d = normalise_input(self._dict_format())
        wh_l, ag_l, pkgs_l = normalise_input(self._list_format())
        self.assertEqual(wh_d, wh_l)
        self.assertEqual(ag_d, ag_l)
        self.assertEqual(pkgs_d[0]["warehouse"], pkgs_l[0]["warehouse"])


class TestAssignPackages(unittest.TestCase):
    """Test nearest-agent assignment logic."""

    def setUp(self):
        self.warehouses = {"W1": [0.0, 0.0], "W2": [100.0, 0.0]}
        self.agents = {
            "A1": [5.0, 0.0],    # close to W1 (dist=5)
            "A2": [95.0, 0.0],   # close to W2 (dist=5)
        }

    def test_nearest_agent_gets_package(self):
        packages = [{"id": "P1", "warehouse": "W1", "destination": [10, 10]}]
        queues = assign_packages(packages, self.warehouses, self.agents)
        self.assertIn("P1", [p["id"] for p in queues["A1"]])
        self.assertEqual(queues["A2"], [])

    def test_agent_near_second_warehouse(self):
        packages = [{"id": "P1", "warehouse": "W2", "destination": [90, 5]}]
        queues = assign_packages(packages, self.warehouses, self.agents)
        self.assertIn("P1", [p["id"] for p in queues["A2"]])

    def test_tie_breaks_lexicographically(self):
        """Two agents equidistant from warehouse – smaller ID wins."""
        warehouses = {"W1": [50.0, 0.0]}
        agents = {"A2": [0.0, 0.0], "A1": [100.0, 0.0]}  # both dist=50 from W1
        packages = [{"id": "P1", "warehouse": "W1", "destination": [50, 10]}]
        queues = assign_packages(packages, warehouses, agents)
        self.assertIn("P1", [p["id"] for p in queues["A1"]])

    def test_idle_agents_still_in_report(self):
        packages = [{"id": "P1", "warehouse": "W1", "destination": [10, 10]}]
        queues = assign_packages(packages, self.warehouses, self.agents)
        # A2 is idle but must still appear
        self.assertIn("A2", queues)
        self.assertEqual(queues["A2"], [])


class TestSimulateDeliveries(unittest.TestCase):
    """Test sequential route distance calculation."""

    def test_single_package_distance(self):
        """
        Agent A1 at (0,0), warehouse W1 at (3,4), destination (6,8).
        Leg1: (0,0)->(3,4) = 5
        Leg2: (3,4)->(6,8) = 5
        Total = 10
        """
        warehouses = {"W1": [3.0, 4.0]}
        agents = {"A1": [0.0, 0.0]}
        queues = {"A1": [{"id": "P1", "warehouse": "W1", "destination": [6.0, 8.0]}]}
        results = simulate_deliveries(queues, warehouses, agents)
        self.assertAlmostEqual(results["A1"]["total_distance"], 10.0)
        self.assertEqual(results["A1"]["packages_delivered"], 1)

    def test_sequential_position_update(self):
        """
        After delivering P1, agent position must update to P1's destination
        before travelling to P2's warehouse.
        """
        warehouses = {"W1": [0.0, 0.0]}
        agents = {"A1": [0.0, 0.0]}
        queues = {
            "A1": [
                {"id": "P1", "warehouse": "W1", "destination": [10.0, 0.0]},
                # Agent is now at (10,0); warehouse W1 is at (0,0)
                # Leg1: (10,0)->(0,0) = 10; Leg2: (0,0)->(5,0) = 5
                {"id": "P2", "warehouse": "W1", "destination": [5.0, 0.0]},
            ]
        }
        results = simulate_deliveries(queues, warehouses, agents)
        # P1: 0+0=0 (start=warehouse) + 10 = 10
        # P2: 10 + 5 = 15
        # Total = 25
        self.assertAlmostEqual(results["A1"]["total_distance"], 25.0)

    def test_zero_package_agent(self):
        """An idle agent has 0 distance and 0 packages."""
        warehouses = {"W1": [10.0, 10.0]}
        agents = {"A1": [0.0, 0.0]}
        queues = {"A1": []}
        results = simulate_deliveries(queues, warehouses, agents)
        self.assertEqual(results["A1"]["packages_delivered"], 0)
        self.assertAlmostEqual(results["A1"]["total_distance"], 0.0)


class TestGenerateReport(unittest.TestCase):
    """Test report values and best-agent selection."""

    def _make_results(self):
        return {
            "A1": {"packages_delivered": 2, "total_distance": 80.0, "route": []},
            "A2": {"packages_delivered": 4, "total_distance": 120.0, "route": []},
            "A3": {"packages_delivered": 0, "total_distance": 0.0, "route": []},
        }

    def test_efficiency_calculation(self):
        report = generate_report(self._make_results())
        # A1: 80/2 = 40.0; A2: 120/4 = 30.0
        self.assertAlmostEqual(report["A1"]["efficiency"], 40.0)
        self.assertAlmostEqual(report["A2"]["efficiency"], 30.0)

    def test_zero_package_agent_efficiency_is_zero(self):
        report = generate_report(self._make_results())
        self.assertAlmostEqual(report["A3"]["efficiency"], 0.0)

    def test_best_agent_ignores_idle_agents(self):
        """A3 has 0 packages (efficiency=0.0) but must NOT be best_agent."""
        report = generate_report(self._make_results())
        # Best = lowest efficiency among active agents: A2 (30.0) < A1 (40.0)
        self.assertEqual(report["best_agent"], "A2")

    def test_best_agent_none_when_no_packages(self):
        results = {
            "A1": {"packages_delivered": 0, "total_distance": 0.0, "route": []},
        }
        best = calculate_best_agent(results)
        self.assertIsNone(best)

    def test_rounding_two_decimal_places(self):
        results = {
            "A1": {"packages_delivered": 3, "total_distance": 100.0 / 3, "route": []},
        }
        report = generate_report(results)
        # 100/3 = 33.333... -> rounded to 33.33
        self.assertEqual(report["A1"]["total_distance"], round(100.0 / 3, 2))
        self.assertEqual(report["A1"]["efficiency"], round(100.0 / 9, 2))


class TestValidateDeliveryCompleteness(unittest.TestCase):
    """Test that the integrity check catches mismatches."""

    def test_passes_when_counts_match(self):
        packages = [{"id": "P1"}, {"id": "P2"}]
        results = {
            "A1": {"packages_delivered": 1},
            "A2": {"packages_delivered": 1},
        }
        # Should not raise
        validate_delivery_completeness(packages, results)

    def test_raises_when_counts_mismatch(self):
        packages = [{"id": "P1"}, {"id": "P2"}]
        results = {"A1": {"packages_delivered": 1}}  # only 1, expected 2
        with self.assertRaises(RuntimeError):
            validate_delivery_completeness(packages, results)


if __name__ == "__main__":
    unittest.main()
