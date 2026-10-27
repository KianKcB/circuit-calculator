"""Tests for the validated circuit data model."""

import math
import unittest
from decimal import Decimal

from circuit_calculator.circuit import Circuit, CurrentSource, Resistor, VoltageSource


class ElementTests(unittest.TestCase):
    def test_constructs_elements_and_normalizes_numeric_values(self):
        resistor = Resistor("R1", "n1", "n2", 100)
        source = VoltageSource("V1", "n1", "n2", Decimal("-5"))
        current = CurrentSource("I1", "n2", "n1", 0)

        self.assertEqual(resistor.resistance_ohms, 100.0)
        self.assertEqual(source.voltage_volts, -5.0)
        self.assertEqual(current.current_amperes, 0.0)
        with self.assertRaises(AttributeError):
            resistor.resistance_ohms = 10

    def test_rejects_invalid_names(self):
        for name in (None, 1, []):
            with self.subTest(name=name):
                with self.assertRaises(TypeError):
                    Resistor(name, "n1", "n2", 1)
        for name in ("", "   "):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    Resistor("R1", name, "n2", 1)

    def test_rejects_self_connections_for_each_element_type(self):
        with self.assertRaisesRegex(ValueError, "distinct nodes"):
            Resistor("R1", "n", "n", 1)
        with self.assertRaisesRegex(ValueError, "distinct nodes"):
            VoltageSource("V1", "n", "n", 1)
        with self.assertRaisesRegex(ValueError, "distinct nodes"):
            CurrentSource("I1", "n", "n", 1)

    def test_resistor_must_be_finite_real_and_strictly_positive(self):
        for resistance in (0, -1):
            with self.subTest(resistance=resistance):
                with self.assertRaises(ValueError):
                    Resistor("R1", "n1", "n2", resistance)
        for resistance in (True, "2", 1 + 2j, None, object()):
            with self.subTest(resistance=resistance):
                with self.assertRaises(TypeError):
                    Resistor("R1", "n1", "n2", resistance)
        for resistance in (math.nan, math.inf, -math.inf, Decimal("NaN")):
            with self.subTest(resistance=resistance):
                with self.assertRaises(ValueError):
                    Resistor("R1", "n1", "n2", resistance)

    def test_sources_accept_signed_finite_values_and_reject_invalid_values(self):
        self.assertEqual(VoltageSource("V1", "a", "b", -3).voltage_volts, -3.0)
        self.assertEqual(CurrentSource("I1", "a", "b", -2).current_amperes, -2.0)
        for source_type in (VoltageSource, CurrentSource):
            for value in (True, "1", 1 + 2j, None, object()):
                with self.subTest(source_type=source_type, value=value):
                    with self.assertRaises(TypeError):
                        source_type("S1", "a", "b", value)
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(source_type=source_type, value=value):
                    with self.assertRaises(ValueError):
                        source_type("S1", "a", "b", value)


class CircuitTests(unittest.TestCase):
    def test_constructs_circuit_from_iterables_and_reference_node(self):
        circuit = Circuit(
            nodes=["n1", "n2"],
            elements=[Resistor("R1", "n1", "n2", 100)],
            reference_node="n2",
        )
        self.assertEqual(circuit.nodes, ("n1", "n2"))
        self.assertEqual(len(circuit.elements), 1)
        self.assertEqual(circuit.reference_node, "n2")
        self.assertIsInstance(circuit.nodes, tuple)
        self.assertIsInstance(circuit.elements, tuple)

    def test_allows_missing_reference_node_and_empty_element_list(self):
        circuit = Circuit(nodes=("n1",), elements=())
        self.assertIsNone(circuit.reference_node)
        self.assertEqual(circuit.elements, ())

    def test_rejects_invalid_or_duplicate_nodes(self):
        for nodes in ((), ("n1", "n1"), ("n1", " "), ("n1", 2), "n1"):
            with self.subTest(nodes=nodes):
                with self.assertRaises((TypeError, ValueError)):
                    Circuit(nodes, ())

    def test_rejects_duplicate_element_names_and_unsupported_elements(self):
        with self.assertRaisesRegex(ValueError, "element names must be unique"):
            Circuit(
                ("a", "b"),
                (Resistor("R1", "a", "b", 1), VoltageSource("R1", "a", "b", 1)),
            )
        with self.assertRaisesRegex(TypeError, "elements must be"):
            Circuit(("a", "b"), (object(),))

    def test_rejects_undeclared_endpoints_for_all_element_types(self):
        elements = (
            Resistor("R1", "a", "missing", 1),
            VoltageSource("V1", "missing", "a", 1),
            CurrentSource("I1", "a", "missing", 1),
        )
        for element in elements:
            with self.subTest(element=element):
                with self.assertRaisesRegex(ValueError, "undeclared node"):
                    Circuit(("a", "b"), (element,))

    def test_allows_distinct_elements_on_the_same_node_pair(self):
        circuit = Circuit(
            ("a", "b"),
            (Resistor("R1", "a", "b", 10), Resistor("R2", "a", "b", 20)),
        )
        self.assertEqual(len(circuit.elements), 2)

    def test_validates_reference_node(self):
        with self.assertRaisesRegex(ValueError, "reference_node"):
            Circuit(("a", "b"), (), reference_node="missing")
        with self.assertRaises(TypeError):
            Circuit(("a",), (), reference_node=1)
        with self.assertRaises(ValueError):
            Circuit(("a",), (), reference_node=" ")


if __name__ == "__main__":
    unittest.main()
