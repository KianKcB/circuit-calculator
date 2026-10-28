"""CSV values, quoting, path protection and atomic output; no NumPy required."""

from contextlib import redirect_stderr, redirect_stdout
import csv
from dataclasses import replace
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from circuit_calculator.dc import DCResult, ElementResult
from circuit_calculator.results_io import HEADER, dumps_results_csv, save_results_csv
from circuit_calculator.circuit_io import save_document
from circuit_calculator.schematic import divider_example
from circuit_calculator.cli import main


def reference_result():
    return DCResult('g', {'g': 0., 'in': 12., 'out': 8.}, {
        'V1': ElementResult(12., -.004, -.048), 'R1': ElementResult(4., .004, .016),
        'R2': ElementResult(8., .004, .032)}, 1., 0., 0.)


def rows(result):
    return list(csv.DictReader(io.StringIO(dumps_results_csv(result), newline='')))


class ResultsCSVTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parent / '.build-check'
        scratch.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.path = self.folder / 'results.csv'

    def test_independent_divider_values_units_reference_and_power_signs(self):
        data = rows(reference_result())
        self.assertEqual(tuple(data[0]), HEADER)
        self.assertEqual(data[0], dict(zip(HEADER, ('1', 'reference', 'node:g', 'voltage', '0.0', 'V'))))
        values = {(r['identifier'], r['quantity']): (float(r['value']), r['unit']) for r in data}
        self.assertEqual(values['node:out', 'voltage'], (8., 'V'))
        self.assertEqual(values['element:R1', 'current'], (.004, 'A'))
        self.assertEqual(values['element:V1', 'power'], (-.048, 'W'))
        self.assertEqual(values['analysis', 'scaled_condition_number'], (1., '1'))
        self.assertEqual(sum(float(r['value']) for r in data if r['entity_type'] == 'element' and r['quantity'] == 'power'), 0)

    def test_deterministic_exact_float_text_and_crlf(self):
        value = 1.2345678901234567
        result = replace(reference_result(), node_voltages={'g': 0., 'precise': value, 'tiny': 5e-324})
        text = dumps_results_csv(result)
        self.assertEqual(text, dumps_results_csv(result))
        self.assertTrue(text.endswith('\r\n'))
        data = rows(result)
        self.assertEqual(float(next(r['value'] for r in data if r['identifier'] == 'node:precise')), value)
        self.assertEqual(float(next(r['value'] for r in data if r['identifier'] == 'node:tiny')), 5e-324)

    def test_unicode_quotes_commas_controls_and_literal_identifiers(self):
        name = '=SUM(1,2)\r\n"مدار"\t'
        result = replace(reference_result(), node_voltages={'g': 0., name: 2.},
                         elements={name: ElementResult(2., -3., -6.)})
        data = rows(result)
        identifiers = {r['identifier'] for r in data}
        self.assertIn('node:' + name, identifiers)
        self.assertIn('element:' + name, identifiers)
        self.assertTrue(all(not r['identifier'].startswith(('=', '+', '-', '@', '\t', '\r', '\n')) for r in data))

    def test_invalid_result_types_references_names_and_values(self):
        result = reference_result()
        invalid = (None, replace(result, node_voltages=None), replace(result, elements=[]),
            replace(result, reference_node='missing'), replace(result, node_voltages={'g': 1.}),
            replace(result, elements={'bad': object()}), replace(result, node_voltages={'g': 0., '': 1.}),
            replace(result, node_voltages={'g': 0., 'x': True}),
            replace(result, node_voltages={'g': 0., 'x': float('inf')}),
            replace(result, elements={'x': ElementResult(1., float('nan'), 1.)}),
            replace(result, scaled_condition_number=float('inf')),
            replace(result, max_kcl_residual_amperes='bad'),
            replace(result, node_voltages={'g': 0., '\ud800': 1.}))
        for value in invalid:
            with self.subTest(result=repr(value)), self.assertRaises((TypeError, ValueError)):
                dumps_results_csv(value)

    def test_atomic_save_no_clobber_and_explicit_replace(self):
        save_results_csv(reference_result(), self.path)
        original = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            save_results_csv(reference_result(), self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.path.write_bytes(b'old')
        save_results_csv(reference_result(), self.path, overwrite=True)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(set(self.folder.iterdir()), {self.path})
        with self.assertRaises(TypeError):
            save_results_csv(reference_result(), self.path, overwrite=1)

    def test_serialization_and_write_failure_preserve_destination_and_cleanup(self):
        self.path.write_bytes(b'original')
        with self.assertRaises(ValueError):
            save_results_csv(replace(reference_result(), power_balance_watts=float('nan')), self.path, overwrite=True)
        with patch('circuit_calculator.results_io.MAX_BYTES', 10), self.assertRaises(ValueError):
            save_results_csv(reference_result(), self.path, overwrite=True)
        with patch('circuit_calculator._document_io.os.replace', side_effect=PermissionError('simulated')), self.assertRaises(PermissionError):
            save_results_csv(reference_result(), self.path, overwrite=True)
        self.assertEqual(self.path.read_bytes(), b'original')
        self.assertEqual(set(self.folder.iterdir()), {self.path})

    def test_input_project_path_and_hardlink_alias_are_protected(self):
        protected = self.folder / 'circuit.json'
        protected.write_bytes(b'input')
        alias = self.folder / 'alias.csv'
        os.link(protected, alias)
        for output in (protected, self.folder / '.' / 'circuit.json', alias):
            with self.subTest(path=output), self.assertRaisesRegex(ValueError, 'protected'):
                save_results_csv(reference_result(), output, overwrite=True, protected_path=protected)
        self.assertEqual(protected.read_bytes(), b'input')
        self.assertEqual(alias.read_bytes(), b'input')

    def test_symlink_alias_is_protected_without_requiring_symlink_privilege(self):
        # resolve() behavior is enough to exercise the policy on Windows systems
        # where creating symlinks requires an OS privilege not needed by the app.
        self.path.write_bytes(b'input')
        with patch.object(Path, 'resolve', return_value=self.path), self.assertRaisesRegex(ValueError, 'protected'):
            save_results_csv(reference_result(), self.folder / 'alias', protected_path=self.path)
        self.assertEqual(self.path.read_bytes(), b'input')

    def run_command(self, argv):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(argv)
        return code, output.getvalue(), errors.getvalue()

    def test_cli_default_json_and_optional_csv_match_same_result(self):
        circuit_path = self.folder / 'circuit.json'
        save_document(divider_example().compile(), circuit_path)
        with patch('circuit_calculator.dc.solve_dc', return_value=reference_result()):
            first = self.run_command(['dc', str(circuit_path)])
            second = self.run_command(['dc', str(circuit_path), '--csv', str(self.path)])
        self.assertEqual(first, second)
        self.assertEqual(first[0], 0)
        self.assertEqual(json.loads(first[1])['node_voltages_volts']['out'], 8)
        with self.path.open(encoding='utf-8', newline='') as stream:
            self.assertEqual(list(csv.DictReader(stream)), rows(reference_result()))

    def test_cli_existing_output_and_protected_input_fail_without_json(self):
        circuit_path = self.folder / 'circuit.json'
        save_document(divider_example().compile(), circuit_path)
        original = circuit_path.read_bytes()
        self.path.write_bytes(b'old')
        with patch('circuit_calculator.dc.solve_dc', return_value=reference_result()):
            code, output, errors = self.run_command(['dc', str(circuit_path), '--csv', str(self.path)])
            self.assertEqual((code, output), (1, ''))
            self.assertTrue(errors.startswith('Error:'))
            self.assertEqual(self.path.read_bytes(), b'old')
            code, _, _ = self.run_command(['dc', str(circuit_path), '--csv', str(self.path), '--overwrite-csv'])
            self.assertEqual(code, 0)
            code, output, errors = self.run_command(['dc', str(circuit_path), '--csv', str(circuit_path), '--overwrite-csv'])
            self.assertEqual((code, output), (1, ''))
            self.assertIn('protected', errors)
        self.assertEqual(circuit_path.read_bytes(), original)

    def test_cli_no_csv_after_solver_failure_and_overwrite_flag_requires_path(self):
        circuit_path = self.folder / 'circuit.json'
        save_document(divider_example().compile(), circuit_path)
        with patch('circuit_calculator.dc.solve_dc', side_effect=ValueError('cannot solve')):
            code, output, _ = self.run_command(['dc', str(circuit_path), '--csv', str(self.path)])
        self.assertEqual((code, output), (1, ''))
        self.assertFalse(self.path.exists())
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
            main(['dc', str(circuit_path), '--overwrite-csv'])
        self.assertEqual(failure.exception.code, 2)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
    def test_actual_solver_csv_preserves_analytical_divider(self):
        from circuit_calculator.dc import solve_dc
        data = rows(solve_dc(divider_example().compile().circuit))
        self.assertAlmostEqual(float(next(r['value'] for r in data if r['identifier'] == 'node:out')), 8)
        self.assertAlmostEqual(float(next(r['value'] for r in data if r['identifier'] == 'element:V1' and r['quantity'] == 'power')), -.048)


if __name__ == '__main__':
    unittest.main()
