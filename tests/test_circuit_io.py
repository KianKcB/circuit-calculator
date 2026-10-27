"""Native-format contracts, malformed inputs, file safety and DC round trips."""

from dataclasses import FrozenInstanceError
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from circuit_calculator.circuit import Circuit, CurrentSource, Resistor, VoltageSource
from circuit_calculator.circuit_io import (CircuitDocument, CircuitFormatError, dumps_document,
                        loads_document, load_document, save_document, MAX_BYTES)


def example():
    return CircuitDocument(Circuit(('g', 'in', 'out'), (
        VoltageSource('V1', 'in', 'g', 12), Resistor('R1', 'in', 'out', 1000),
        Resistor('R2', 'out', 'g', 2000), CurrentSource('I1', 'g', 'out', -.001)), 'g'),
        'مدار', 'Unicode, "quotes", backslash \\ and brackets [{ preserved.')


def data():
    return json.loads(dumps_document(example()))


class DocumentTests(unittest.TestCase):
    def test_all_elements_metadata_order_and_float_values_round_trip(self):
        document = example()
        restored = loads_document(dumps_document(document))
        self.assertEqual(restored, document)
        self.assertEqual(restored.circuit.nodes, ('g', 'in', 'out'))
        self.assertEqual([e.name for e in restored.circuit.elements], ['V1', 'R1', 'R2', 'I1'])
        self.assertIsInstance(restored.circuit.elements[0].voltage_volts, float)
        with self.assertRaises(FrozenInstanceError):
            restored.title = 'changed'

    def test_deterministic_normalized_output(self):
        text = dumps_document(example())
        self.assertEqual(text, dumps_document(example()))
        self.assertEqual(text, dumps_document(loads_document(text)))
        self.assertTrue(text.endswith('\n'))
        self.assertIn('مدار', text)
        self.assertEqual(list(json.loads(text)), ['circuit', 'format', 'metadata', 'version'])

    def test_missing_reference_disconnected_and_empty_elements_are_preserved(self):
        document = CircuitDocument(Circuit(('g', 'unused'), ()))
        self.assertEqual(loads_document(dumps_document(document)), document)

    def test_signed_zero_and_subnormal_sources(self):
        document = CircuitDocument(Circuit(('g', 'a'),
            (VoltageSource('V', 'a', 'g', -0.0), CurrentSource('I', 'g', 'a', 5e-324)), 'g'))
        text = dumps_document(document)
        self.assertIn('-0.0', text)
        self.assertEqual(loads_document(text), document)

    def test_invalid_api_arguments(self):
        for value in (None, b'{}', {}):
            with self.subTest(value=value), self.assertRaises(TypeError):
                loads_document(value)
        with self.assertRaises(TypeError):
            dumps_document(example().circuit)
        with self.assertRaises(TypeError):
            CircuitDocument(None)
        with self.assertRaises(CircuitFormatError):
            CircuitDocument(example().circuit, title=1)

    def test_unknown_component_subclasses_do_not_lose_data(self):
        class SpecialResistor(Resistor):
            pass
        circuit = Circuit(('g', 'a'), (SpecialResistor('R', 'a', 'g', 1),), 'g')
        with self.assertRaisesRegex(CircuitFormatError, 'unsupported element'):
            dumps_document(CircuitDocument(circuit))


class InvalidDocumentTests(unittest.TestCase):
    def reject(self, value, message=None):
        with self.assertRaisesRegex(CircuitFormatError, message or '.'):
            loads_document(json.dumps(value))

    def test_root_type_and_format(self):
        for value in ([], None, 1, 'circuit'):
            self.reject(value, 'object')
        value = data()
        value['format'] = 'spice'
        self.reject(value, 'format')

    def test_versions_are_strict(self):
        for version in (True, 1.0, '1', 0, 2, None):
            value = data()
            value['version'] = version
            self.reject(value, 'version')

    def test_missing_and_unknown_fields_at_every_level(self):
        for location in ('root', 'metadata', 'circuit', 'element'):
            for unknown in (True, False):
                value = data()
                target = {'root': value, 'metadata': value['metadata'],
                          'circuit': value['circuit'], 'element': value['circuit']['elements'][0]}[location]
                if unknown:
                    target['unexpected'] = 'no implicit extensions'
                else:
                    del target[next(iter(target))]
                with self.subTest(location=location, unknown=unknown):
                    self.reject(value)

    def test_duplicate_keys_at_root_and_nested_level(self):
        text = dumps_document(example())
        for changed in (text.replace('"version": 1', '"version": 1, "version": 1'),
                        text.replace('"title":', '"title": "discarded", "title":')):
            with self.subTest(text=changed), self.assertRaisesRegex(CircuitFormatError, 'duplicate'):
                loads_document(changed)

    def test_unknown_element_and_non_object_element(self):
        for element in ({'type': 'capacitor'}, {'type': []}, 1, None):
            value = data()
            value['circuit']['elements'] = [element]
            self.reject(value, r'elements\[0\]')

    def test_names_and_reference_are_not_coerced(self):
        for key, replacement in (('nodes', 'ga'), ('nodes', [1]),
                                 ('nodes', []), ('reference_node', 0), ('elements', {})):
            value = data()
            value['circuit'][key] = replacement
            self.reject(value, 'circuit')

    def test_domain_model_errors_keep_context(self):
        for fault in ('duplicate_node', 'duplicate_element', 'missing_endpoint',
                      'bad_reference', 'self_connection', 'empty_name', 'zero_resistor'):
            value = data()
            circuit = value['circuit']
            if fault == 'duplicate_node':
                circuit['nodes'].append('g')
            elif fault == 'duplicate_element':
                circuit['elements'][1]['name'] = 'V1'
            elif fault == 'missing_endpoint':
                circuit['elements'][0]['plus_node'] = 'missing'
            elif fault == 'bad_reference':
                circuit['reference_node'] = 'missing'
            elif fault == 'self_connection':
                circuit['elements'][0]['plus_node'] = 'g'
            elif fault == 'empty_name':
                circuit['elements'][0]['name'] = ' '
            else:
                circuit['elements'][1]['resistance_ohms'] = 0
            with self.subTest(fault=fault):
                self.reject(value, 'circuit')

    def test_numeric_types_nonfinite_and_expression_strings(self):
        for number in (True, None, '12', '1k', '__import__("os").system("invalid")',
                       [], float('inf'), float('nan')):
            value = data()
            value['circuit']['elements'][0]['voltage_volts'] = number
            with self.subTest(number=number):
                self.reject(value)

    def test_raw_numeric_overflow_and_underflow_cannot_disappear(self):
        text = dumps_document(example())
        for literal in ('1e1000', '1e-1000', '1e99999999999999999999999', '9' * 5000):
            with self.subTest(literal=literal[:30]), self.assertRaises(CircuitFormatError):
                loads_document(text.replace('"voltage_volts": 12.0', '"voltage_volts": ' + literal))

    def test_malformed_json_has_line_and_column(self):
        for text in ('{"version":', '{bad}', '{} trailing', '\ufeff{}'):
            with self.subTest(text=text), self.assertRaisesRegex(CircuitFormatError, 'line .*column'):
                loads_document(text)

    def test_invalid_unicode_literal_and_escaped(self):
        text = dumps_document(example())
        for replacement in ('\ud800', '\\ud800'):
            with self.subTest(replacement=repr(replacement)), self.assertRaisesRegex(CircuitFormatError, 'Unicode'):
                loads_document(text.replace('مدار', replacement))

    def test_byte_limit_counts_utf8_and_applies_to_output(self):
        text = dumps_document(example())
        with patch('circuit_calculator.circuit_io.MAX_BYTES', len(text.encode('utf-8')) - 1):
            with self.assertRaisesRegex(CircuitFormatError, 'bytes'):
                loads_document(text)
            with self.assertRaisesRegex(CircuitFormatError, 'bytes'):
                dumps_document(example())
        with self.assertRaisesRegex(CircuitFormatError, 'bytes'):
            loads_document(' ' * (MAX_BYTES + 1))

    def test_nesting_limit_ignores_escaped_quotes_and_brackets_in_strings(self):
        self.assertEqual(loads_document(dumps_document(example())), example())
        with self.assertRaisesRegex(CircuitFormatError, 'nesting'):
            loads_document('[' * 17 + '0' + ']' * 17)

    def test_node_element_and_string_limits(self):
        for constant, limit in (('MAX_NODES', 2), ('MAX_ELEMENTS', 3), ('MAX_NAME_LENGTH', 2)):
            with patch('circuit_calculator.circuit_io.' + constant, limit):
                with self.subTest(constant=constant), self.assertRaises(CircuitFormatError):
                    loads_document(dumps_document(example()))
        for key, limit in (('title', 256), ('description', 4096)):
            value = data()
            value['metadata'][key] = 'x' * (limit + 1)
            self.reject(value, 'metadata')


class FileTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parent / '.build-check'
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch, prefix='persistence-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory / 'مدار.json'

    def test_save_load_and_explicit_replace(self):
        save_document(example(), self.path)
        self.assertEqual(self.path.read_bytes(), dumps_document(example()).encode('utf-8'))
        self.assertEqual(load_document(self.path), example())
        replacement = CircuitDocument(Circuit(('g',), (), 'g'), 'replacement')
        save_document(replacement, self.path, overwrite=True)
        self.assertEqual(load_document(self.path), replacement)
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_existing_file_is_preserved_by_default(self):
        self.path.write_bytes(b'original content')
        with self.assertRaises(FileExistsError):
            save_document(example(), self.path)
        self.assertEqual(self.path.read_bytes(), b'original content')
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_invalid_document_never_touches_destination(self):
        self.path.write_bytes(b'original content')
        with self.assertRaises(TypeError):
            save_document(None, self.path, overwrite=True)
        with self.assertRaises(TypeError):
            save_document(example(), self.path, overwrite='yes')
        self.assertEqual(self.path.read_bytes(), b'original content')

    def test_failed_replace_preserves_existing_file_and_cleans_temporary(self):
        self.path.write_bytes(b'original content')
        with patch('circuit_calculator._document_io.os.replace', side_effect=PermissionError('simulated failure')):
            with self.assertRaises(PermissionError):
                save_document(example(), self.path, overwrite=True)
        self.assertEqual(self.path.read_bytes(), b'original content')
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_write_failure_cleans_temporary(self):
        with patch('circuit_calculator._document_io.os.fsync', side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):
                save_document(example(), self.path)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_bad_encoding_oversized_and_missing_files(self):
        self.path.write_bytes(b'\xff')
        with self.assertRaisesRegex(CircuitFormatError, 'UTF-8'):
            load_document(self.path)
        self.path.write_bytes(b' ' * (MAX_BYTES + 1))
        with self.assertRaisesRegex(CircuitFormatError, 'bytes'):
            load_document(self.path)
        with self.assertRaises(FileNotFoundError):
            load_document(self.directory / 'missing.json')
        with self.assertRaises(FileNotFoundError):
            save_document(example(), self.directory / 'missing' / 'file.json')

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
    def test_construct_save_load_solve_has_same_physical_result(self):
        from circuit_calculator.dc import solve_dc
        save_document(example(), self.path)
        original = solve_dc(example().circuit)
        restored = solve_dc(load_document(self.path).circuit)
        self.assertEqual(restored, original)
        self.assertAlmostEqual(restored.node_voltages['out'], 22 / 3)
        self.assertAlmostEqual(restored.power_balance_watts, 0)
        self.assertLess(restored.max_kcl_residual_amperes, 1e-12)


if __name__ == '__main__':
    unittest.main()
