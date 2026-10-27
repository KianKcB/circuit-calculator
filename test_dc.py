"""Analytical reference circuits and failure cases for linear DC analysis."""

import importlib.util
import math
import unittest

from circuit import Circuit, CurrentSource as I, Resistor as R, VoltageSource as V
from dc import (assemble_dc, solve_dc, ContradictorySourceError,
                FloatingNetworkError, MissingReferenceError,
                NonUniqueSolutionError, NumericalError, InconsistentCurrentError)


class AssemblyTests(unittest.TestCase):
    def test_hand_derived_mixed_source_matrix(self):
        circuit = Circuit(('g', 'a', 'b'), (
            R('R1', 'a', 'g', 2), R('R2', 'a', 'b', 4),
            V('V', 'b', 'g', 3), I('I', 'g', 'a', 2)), 'g')
        system = assemble_dc(circuit)
        self.assertEqual(system.node_order, ('a', 'b'))
        self.assertEqual(system.source_order, ('V',))
        self.assertEqual(system.matrix, ((.75, -.25, 0), (-.25, .25, 1), (0, 1, 0)))
        self.assertEqual(system.rhs, (2, 0, 3))
        with self.assertRaises(AttributeError):
            system.rhs = ()

    def test_input_and_reference_errors(self):
        with self.assertRaises(TypeError):
            assemble_dc(None)
        with self.assertRaises(MissingReferenceError):
            assemble_dc(Circuit(('g',), ()))

    def test_isolated_and_balanced_current_source_nodes_float(self):
        for elements in ((), (I('I', 'g', 'a', 0),),
                         (R('R', 'a', 'b', 2), I('I1', 'g', 'a', 1), I('I2', 'b', 'g', 1))):
            with self.subTest(elements=elements):
                with self.assertRaises(FloatingNetworkError):
                    assemble_dc(Circuit(('g', 'a', 'b'), elements, 'g'))

    def test_current_source_cutset_violates_kcl(self):
        for elements in ((I('I', 'g', 'a', 1),),
                         (R('R', 'a', 'b', 2), I('I', 'g', 'a', 1))):
            with self.subTest(elements=elements):
                with self.assertRaises(InconsistentCurrentError):
                    assemble_dc(Circuit(('g', 'a', 'b'), elements, 'g'))

    def test_source_loops_distinguish_conflict_and_nonuniqueness(self):
        for voltage, error in ((2, ContradictorySourceError), (1, NonUniqueSolutionError)):
            with self.subTest(voltage=voltage):
                with self.assertRaises(error):
                    assemble_dc(Circuit(('g', 'a'),
                                        (V('V1', 'a', 'g', 1), V('V2', 'a', 'g', voltage)), 'g'))

    def test_three_source_loop_and_reversed_orientation(self):
        for voltage, error in ((-3, NonUniqueSolutionError), (-4, ContradictorySourceError)):
            with self.subTest(voltage=voltage):
                with self.assertRaises(error):
                    assemble_dc(Circuit(('g', 'a', 'b'),
                        (V('V1', 'a', 'g', 1), V('V2', 'b', 'a', 2),
                         V('V3', 'g', 'b', voltage)), 'g'))

    def test_exact_float_constraints_do_not_hide_small_conflicts(self):
        with self.assertRaises(ContradictorySourceError):
            assemble_dc(Circuit(('g', 'a'),
                (V('V1', 'a', 'g', 1), V('V2', 'a', 'g', 1 + 1e-14)), 'g'))

    def test_unsupported_subclass_is_not_silently_treated_as_resistor(self):
        class DifferentResistor(R):
            pass
        with self.assertRaises(TypeError):
            assemble_dc(Circuit(('g', 'a'), (DifferentResistor('R', 'a', 'g', 1),), 'g'))

    def test_assembly_range_failures(self):
        for elements in ((R('R', 'a', 'g', 1e-320),),
                         (R('R1', 'a', 'g', 1e-308), R('R2', 'a', 'g', 1e-308)),
                         (R('R', 'a', 'g', 1), I('I1', 'g', 'a', 1e308),
                          I('I2', 'g', 'a', 1e308))):
            with self.subTest(elements=elements):
                with self.assertRaises(NumericalError):
                    assemble_dc(Circuit(('g', 'a'), elements, 'g'))


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
class SolverTests(unittest.TestCase):
    def check_physics(self, circuit, result):
        """Independent KCL, constitutive relationships and total power checks."""
        kcl = dict.fromkeys(circuit.nodes, 0.0)
        for element in circuit.elements:
            value = result.elements[element.name]
            if isinstance(element, R):
                a, b = element.node_a, element.node_b
                self.assertAlmostEqual(value.current_amperes * element.resistance_ohms,
                                       value.voltage_volts)
            elif isinstance(element, V):
                a, b = element.plus_node, element.minus_node
                self.assertAlmostEqual(value.voltage_volts, element.voltage_volts)
            else:
                a, b = element.from_node, element.to_node
                self.assertEqual(value.current_amperes, element.current_amperes)
            self.assertAlmostEqual(value.voltage_volts,
                                   result.node_voltages[a] - result.node_voltages[b])
            kcl[a] += value.current_amperes
            kcl[b] -= value.current_amperes
            self.assertAlmostEqual(value.power_watts, value.voltage_volts * value.current_amperes)
        for current in kcl.values():
            self.assertAlmostEqual(current, 0)
        self.assertAlmostEqual(math.fsum(v.power_watts for v in result.elements.values()), 0)

    def test_series_divider_and_source_power(self):
        circuit = Circuit(('g', 'in', 'out'),
            (V('Vs', 'in', 'g', 12), R('R1', 'in', 'out', 1000),
             R('R2', 'out', 'g', 2000)), 'g')
        result = solve_dc(circuit)
        self.assertAlmostEqual(result.node_voltages['out'], 8)
        self.assertAlmostEqual(result.elements['Vs'].current_amperes, -.004)
        self.assertAlmostEqual(result.elements['Vs'].power_watts, -.048)
        self.check_physics(circuit, result)

    def test_parallel_current_source(self):
        circuit = Circuit(('a', 'g'),
            (I('I', 'g', 'a', 6), R('R1', 'a', 'g', 2), R('R2', 'a', 'g', 6)), 'g')
        result = solve_dc(circuit)
        self.assertAlmostEqual(result.node_voltages['a'], 9)
        self.assertAlmostEqual(result.elements['R1'].current_amperes, 4.5)
        self.assertAlmostEqual(result.elements['R2'].current_amperes, 1.5)
        self.check_physics(circuit, result)

    def test_supernode(self):
        # Va - Vb = 6; Va/2 + Vb/4 = 0 => Va=2, Vb=-4.
        circuit = Circuit(('g', 'a', 'b'),
            (V('V', 'a', 'b', 6), R('Ra', 'a', 'g', 2), R('Rb', 'b', 'g', 4)), 'g')
        result = solve_dc(circuit)
        self.assertAlmostEqual(result.node_voltages['a'], 2)
        self.assertAlmostEqual(result.node_voltages['b'], -4)
        self.check_physics(circuit, result)

    def test_mixed_and_multiple_voltage_sources(self):
        circuit = Circuit(('g', 'a', 'b', 'c'),
            (V('Va', 'a', 'g', 10), V('Vb', 'b', 'g', -2),
             R('Ra', 'a', 'c', 2), R('Rb', 'c', 'b', 2), I('I', 'g', 'c', 1)), 'g')
        result = solve_dc(circuit)
        self.assertAlmostEqual(result.node_voltages['c'], 5)
        self.check_physics(circuit, result)

    def test_balanced_bridge(self):
        circuit = Circuit(('g', 's', 'a', 'b'),
            (V('V', 's', 'g', 10), R('R1', 's', 'a', 10), R('R2', 'a', 'g', 10),
             R('R3', 's', 'b', 20), R('R4', 'b', 'g', 20), R('bridge', 'a', 'b', 5)), 'g')
        result = solve_dc(circuit)
        self.assertAlmostEqual(result.node_voltages['a'], 5)
        self.assertAlmostEqual(result.node_voltages['b'], 5)
        self.assertAlmostEqual(result.elements['bridge'].current_amperes, 0)
        self.check_physics(circuit, result)

    def test_unbalanced_bridge_against_hand_elimination(self):
        # KCL: a - b/6 = 5; -a/6 + 37*b/60 = 5/2.
        # Eliminating a gives b=300/53 and a=315/53.
        circuit = Circuit(('g', 's', 'a', 'b'),
            (V('V', 's', 'g', 10), R('R1', 's', 'a', 2), R('R2', 'a', 'g', 3),
             R('R3', 's', 'b', 4), R('R4', 'b', 'g', 5), R('bridge', 'a', 'b', 6)), 'g')
        result = solve_dc(circuit)
        self.assertAlmostEqual(result.node_voltages['a'], 315 / 53)
        self.assertAlmostEqual(result.node_voltages['b'], 300 / 53)
        self.assertAlmostEqual(result.elements['bridge'].current_amperes, 5 / 106)
        self.check_physics(circuit, result)

    def test_changing_reference_preserves_branch_results(self):
        elements = (V('V', 'a', 'g', 6), R('R1', 'a', 'b', 2), R('R2', 'b', 'g', 4))
        original = solve_dc(Circuit(('g', 'a', 'b'), elements, 'g'))
        shifted = solve_dc(Circuit(('b', 'g', 'a'), tuple(reversed(elements)), 'b'))
        for name, value in original.elements.items():
            self.assertAlmostEqual(value.voltage_volts, shifted.elements[name].voltage_volts)
            self.assertAlmostEqual(value.current_amperes, shifted.elements[name].current_amperes)
        self.assertAlmostEqual(shifted.node_voltages['g'], -4)

    def test_source_orientation_reversal_and_node_renaming(self):
        first = solve_dc(Circuit(('g', 'a'), (I('I', 'g', 'a', 2), R('R', 'a', 'g', 3)), 'g'))
        second = solve_dc(Circuit(('x', 'ref'), (R('R', 'ref', 'x', 3), I('I', 'x', 'ref', -2)), 'ref'))
        self.assertEqual(first.node_voltages['a'], second.node_voltages['x'])
        self.assertEqual(first.elements['R'].current_amperes, -second.elements['R'].current_amperes)
        self.assertEqual(first.elements['R'].power_watts, second.elements['R'].power_watts)
        forward = solve_dc(Circuit(('g', 'a'), (V('V', 'a', 'g', 2), R('R', 'a', 'g', 3)), 'g'))
        reverse = solve_dc(Circuit(('a', 'g'), (R('R', 'a', 'g', 3), V('V', 'g', 'a', -2)), 'g'))
        self.assertEqual(forward.node_voltages, reverse.node_voltages)
        self.assertEqual(forward.elements['V'].current_amperes, -reverse.elements['V'].current_amperes)

    def test_ground_only_passive_and_zero_voltage_source(self):
        self.assertEqual(dict(solve_dc(Circuit(('g',), (), 'g')).node_voltages), {'g': 0})
        for elements in ((R('R', 'a', 'g', 1),),
                         (V('V', 'a', 'g', 0), I('I', 'g', 'a', 2))):
            circuit = Circuit(('a', 'g'), elements, 'g')
            result = solve_dc(circuit)
            self.assertEqual(result.node_voltages['a'], 0)
            self.check_physics(circuit, result)

    def test_results_are_immutable_and_repeatable(self):
        circuit = Circuit(('g', 'a'), (V('V', 'a', 'g', 1),), 'g')
        result = solve_dc(circuit)
        self.assertEqual(result, solve_dc(circuit))
        with self.assertRaises(TypeError):
            result.node_voltages['a'] = 2
        with self.assertRaises(TypeError):
            result.elements['V'] = None
        with self.assertRaises(AttributeError):
            result.elements['V'].power_watts = 1

    def test_uniform_resistance_scaling(self):
        for resistance in (1e-100, 1, 1e100):
            circuit = Circuit(('g', 'a'), (I('I', 'g', 'a', 2 / resistance),
                                              R('R', 'a', 'g', resistance)), 'g')
            self.assertAlmostEqual(solve_dc(circuit).node_voltages['a'], 2)

    def test_ill_conditioned_network_rejected(self):
        circuit = Circuit(('g', 'a', 'b'),
            (R('weak', 'a', 'g', 1e15), R('strong', 'a', 'b', 1)), 'g')
        with self.assertRaisesRegex(NumericalError, 'ill-conditioned'):
            solve_dc(circuit)

    def test_result_overflow_and_underflow_rejected(self):
        for voltage, resistance in ((1e200, 1), (1e-200, 1e100)):
            with self.subTest(voltage=voltage):
                with self.assertRaises(NumericalError):
                    solve_dc(Circuit(('g', 'a'),
                        (V('V', 'a', 'g', voltage), R('R', 'a', 'g', resistance)), 'g'))


if __name__ == '__main__':
    unittest.main()
