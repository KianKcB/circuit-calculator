"""Native document to CLI results, errors and resource guard integration tests."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from circuit_calculator.circuit import Circuit, Resistor, VoltageSource
from circuit_calculator.circuit_io import CircuitDocument, save_document
from circuit_calculator.cli import main


class DCCommandTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parent / '.build-check'
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch, prefix='dc-command-')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'circuit.json'

    def run_command(self, argv):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(argv)
        return code, output.getvalue(), errors.getvalue()

    def save_example(self):
        save_document(CircuitDocument(Circuit(('g', 'in', 'out'),
            (VoltageSource('V', 'in', 'g', 12), Resistor('R1', 'in', 'out', 1000),
             Resistor('R2', 'out', 'g', 2000)), 'g'), 'Divider'), self.path)

    def test_legacy_no_argument_menu_is_preserved(self):
        with patch('builtins.input', return_value='6'):
            code, output, errors = self.run_command([])
        self.assertEqual(code, 0)
        self.assertIn('Goodbye.', output)
        self.assertEqual(errors, '')

    def test_missing_file_and_bad_json_are_clean_errors(self):
        for content in (None, 'not JSON'):
            if content is not None:
                self.path.write_text(content)
            code, output, errors = self.run_command(['dc', str(self.path)])
            self.assertEqual(code, 1)
            self.assertEqual(output, '')
            self.assertTrue(errors.startswith('Error:'))
            self.assertNotIn('Traceback', errors)

    def test_missing_reference_is_reported_without_output(self):
        save_document(CircuitDocument(Circuit(('g',), ())), self.path)
        code, output, errors = self.run_command(['dc', str(self.path)])
        self.assertEqual(code, 1)
        self.assertEqual(output, '')
        self.assertIn('reference_node', errors)

    def test_dense_size_guard_runs_before_solver(self):
        self.save_example()
        with patch('circuit_calculator.cli.MAX_DC_UNKNOWNS', 2), patch('circuit_calculator.dc.solve_dc') as solve:
            code, output, errors = self.run_command(['dc', str(self.path)])
        solve.assert_not_called()
        self.assertEqual(code, 1)
        self.assertEqual(output, '')
        self.assertIn('at most 2 unknowns', errors)

    def test_missing_numpy_has_actionable_error(self):
        self.save_example()
        with patch('circuit_calculator.dc.solve_dc', side_effect=ImportError('install the [dc] extra')):
            code, output, errors = self.run_command(['dc', str(self.path)])
        self.assertEqual(code, 1)
        self.assertEqual(output, '')
        self.assertIn('[dc]', errors)

    def test_invalid_command_arguments_use_argparse_exit_status(self):
        for arguments in (['dc'], ['unknown']):
            with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main(arguments)
                self.assertEqual(error.exception.code, 2)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
    def test_known_answer_json_results_and_repeatability(self):
        self.save_example()
        code, output, errors = self.run_command(['dc', str(self.path)])
        self.assertEqual(code, 0)
        self.assertEqual(errors, '')
        result = json.loads(output)
        self.assertEqual(result['title'], 'Divider')
        self.assertEqual(result['reference_node'], 'g')
        self.assertAlmostEqual(result['node_voltages_volts']['out'], 8)
        self.assertAlmostEqual(result['elements']['R1']['current_amperes'], .004)
        self.assertAlmostEqual(result['elements']['V']['power_watts'], -.048)
        self.assertAlmostEqual(result['diagnostics']['power_balance_watts'], 0)
        self.assertEqual(self.run_command(['dc', str(self.path)])[1], output)


if __name__ == '__main__':
    unittest.main()
