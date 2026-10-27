"""Strict project parsing, atomic save semantics and full editor round trips."""

from dataclasses import replace, FrozenInstanceError
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from circuit_calculator.circuit import Circuit
from circuit_calculator.circuit_io import CircuitDocument, dumps_document, loads_document, CircuitFormatError
from circuit_calculator.schematic import Schematic, Wire, divider_example
from circuit_calculator.project_io import (SchematicProject, ViewState, ProjectFormatError,
                                           dumps_project, loads_project, save_project, load_project)


def example():
    state = divider_example().move_node('out', 560, -80)
    document = replace(state.document, title='مدار', description='Layout, wires and zoom preserved.')
    return SchematicProject(replace(state, document=document), ViewState(1.25, .2, .3))


def data():
    return json.loads(dumps_project(example()))


class ProjectTests(unittest.TestCase):
    def reject(self, value, message='.'):
        with self.assertRaisesRegex(ProjectFormatError, message):
            loads_project(json.dumps(value))

    def test_complete_round_trip_preserves_uncompiled_alias_junctions(self):
        project = example()
        loaded = loads_project(dumps_project(project))
        self.assertEqual(loaded, project)
        self.assertEqual(loaded.schematic.document.circuit.nodes, ('g', 'in', 'out', 'return'))
        self.assertEqual(loaded.schematic.wires, (Wire('W1', 'return', 'g'),))
        self.assertEqual(loaded.view, ViewState(1.25, .2, .3))
        alternate = replace(project, schematic=project.schematic.set_reference('return'))
        self.assertEqual(loads_project(dumps_project(alternate)).schematic.document.circuit.reference_node, 'return')
        with self.assertRaises(FrozenInstanceError):
            loaded.view.zoom = 2

    def test_output_is_deterministic_and_normalized(self):
        text = dumps_project(example())
        self.assertEqual(text, dumps_project(example()))
        self.assertEqual(text, dumps_project(loads_project(text)))
        self.assertTrue(text.endswith('\n'))
        self.assertIn('مدار', text)

    def test_unfinished_unsolvable_editor_states_can_be_saved(self):
        for state in (Schematic.from_document(CircuitDocument(Circuit(('n1',), ()))),
                      divider_example().add_wire(Wire('short', 'in', 'out'))):
            with self.subTest(state=state):
                self.assertEqual(loads_project(dumps_project(SchematicProject(state))).schematic, state)

    def test_formats_are_distinct_and_native_round_trips_unchanged(self):
        native = dumps_document(example().schematic.compile())
        self.assertEqual(dumps_document(loads_document(native)), native)
        with self.assertRaises(ProjectFormatError):
            loads_project(native)
        with self.assertRaises(CircuitFormatError):
            loads_document(dumps_project(example()))

    def test_api_types_and_view_normalization(self):
        with self.assertRaises(TypeError):
            dumps_project(None)
        with self.assertRaises(TypeError):
            loads_project(b'{}')
        with self.assertRaises(TypeError):
            SchematicProject(None)
        self.assertEqual(ViewState(Decimal('1.25'), 0, 1), ViewState(1.25, 0.0, 1.0))

    def test_root_and_version_validation(self):
        for value in (None, [], 1, 'project'):
            self.reject(value, 'object')
        for version in (True, 1.0, '1', None, 0, 2):
            value = data()
            value['version'] = version
            self.reject(value, 'version')

    def test_unknown_and_missing_fields_at_all_levels(self):
        for level in ('root', 'layout', 'position', 'wire', 'view', 'document'):
            for missing in (True, False):
                value = data()
                target = {'root': value, 'layout': value['layout'],
                          'position': value['layout']['positions'][0], 'wire': value['layout']['wires'][0],
                          'view': value['view'], 'document': value['document']}[level]
                if missing:
                    del target[next(iter(target))]
                else:
                    target['unexpected'] = True
                with self.subTest(level=level, missing=missing):
                    self.reject(value)

    def test_duplicate_keys_and_malformed_json(self):
        text = dumps_project(example())
        for changed in (text.replace('"zoom": 1.25', '"zoom": 1.25, "zoom": 1'),
                        text.replace('"title":', '"title": "lost", "title":')):
            with self.assertRaisesRegex(ProjectFormatError, 'duplicate'):
                loads_project(changed)
        with self.assertRaisesRegex(ProjectFormatError, 'line .*column'):
            loads_project('{bad}')

    def test_numeric_and_string_coercion_is_rejected(self):
        for number in (True, '1', None, [], float('inf'), float('nan'), 10**400):
            for field in ('zoom', 'x'):
                value = data()
                target = value['view'] if field == 'zoom' else value['layout']['positions'][0]
                target[field] = number
                with self.subTest(number=number, field=field):
                    self.reject(value)

    def test_raw_numeric_underflow_and_huge_exponent(self):
        text = dumps_project(example())
        for literal in ('1e-1000', '1e1000', '1e99999999999999999999999'):
            with self.subTest(literal=literal), self.assertRaises(ProjectFormatError):
                loads_project(text.replace('"zoom": 1.25', '"zoom": ' + literal))

    def test_coordinate_and_view_range(self):
        for field, values in (('zoom', (.39, 2.51)), ('scroll_x', (-.1, 1.1)), ('scroll_y', (-1, 2))):
            for number in values:
                value = data()
                value['view'][field] = number
                self.reject(value, 'view')
        value = data()
        value['layout']['positions'][0]['x'] = 100001
        self.reject(value, 'coordinates')

    def test_positions_must_exactly_match_declared_nodes(self):
        for change in ('missing', 'duplicate', 'undeclared', 'not_array'):
            value = data()
            positions = value['layout']['positions']
            if change == 'missing':
                positions.pop()
            elif change == 'duplicate':
                positions[1]['node'] = positions[0]['node']
            elif change == 'undeclared':
                positions[0]['node'] = 'missing'
            else:
                value['layout']['positions'] = {}
            with self.subTest(change=change):
                self.reject(value, 'position')

    def test_invalid_wires_and_count_limit(self):
        for change in ('name', 'endpoint', 'self', 'pair', 'duplicate_name', 'not_array', 'count'):
            value = data()
            wires = value['layout']['wires']
            if change == 'name':
                wires[0]['name'] = ' '
            elif change == 'endpoint':
                wires[0]['first'] = 'missing'
            elif change == 'self':
                wires[0]['second'] = wires[0]['first']
            elif change == 'pair':
                wires.append({'name': 'W2', 'first': 'g', 'second': 'return'})
            elif change == 'duplicate_name':
                wires.append({'name': 'W1', 'first': 'g', 'second': 'out'})
            elif change == 'not_array':
                value['layout']['wires'] = 'wire'
            else:
                value['layout']['wires'] *= 401
            with self.subTest(change=change):
                self.reject(value)

    def test_embedded_document_validation_and_editor_limits(self):
        value = data()
        value['document']['circuit']['elements'][0]['plus_node'] = 'missing'
        self.reject(value, 'document')
        value = data()
        value['document']['circuit']['nodes'] = [str(i) for i in range(101)]
        value['document']['circuit']['elements'] = []
        value['document']['circuit']['reference_node'] = None
        self.reject(value, 'editor')

    def test_unicode_strings_and_length_limits(self):
        value = data()
        value['layout']['wires'][0]['name'] = '\ud800'
        self.reject(value, 'Unicode')
        value = data()
        value['layout']['wires'][0]['name'] = 'x' * 257
        self.reject(value, '256')

    def test_byte_and_depth_limits_apply_to_load_and_dump(self):
        text = dumps_project(example())
        with patch('circuit_calculator.project_io.MAX_BYTES', len(text.encode('utf-8')) - 1):
            with self.assertRaisesRegex(ProjectFormatError, 'bytes'):
                loads_project(text)
            with self.assertRaisesRegex(ProjectFormatError, 'bytes'):
                dumps_project(example())
        with self.assertRaisesRegex(ProjectFormatError, 'nesting'):
            loads_project('[' * 17 + '0' + ']' * 17)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
    def test_project_round_trip_and_electrical_export_have_same_solution(self):
        from circuit_calculator.dc import solve_dc
        loaded = loads_project(dumps_project(example()))
        result = solve_dc(loaded.schematic.compile().circuit)
        self.assertAlmostEqual(result.node_voltages['out'], 8)
        self.assertAlmostEqual(result.elements['V1'].power_watts, -.048)
        self.assertEqual(result, solve_dc(example().schematic.compile().circuit))


class ProjectFileTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parent / '.build-check'
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'project.ccproj.json'

    def test_create_refuse_clobber_and_replace(self):
        save_project(example(), self.path)
        self.assertEqual(load_project(self.path), example())
        with self.assertRaises(FileExistsError):
            save_project(example(), self.path)
        other = replace(example(), view=ViewState(2, .1, .2))
        save_project(other, self.path, overwrite=True)
        self.assertEqual(load_project(self.path), other)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_failed_save_preserves_destination_and_cleans_temporary(self):
        self.path.write_bytes(b'original')
        with patch('circuit_calculator._document_io.os.replace', side_effect=PermissionError('simulated')):
            with self.assertRaises(PermissionError):
                save_project(example(), self.path, overwrite=True)
        self.assertEqual(self.path.read_bytes(), b'original')
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        with self.assertRaises(TypeError):
            save_project(None, self.path, overwrite=True)
        self.assertEqual(self.path.read_bytes(), b'original')

    def test_bad_encoding_size_and_missing_file(self):
        self.path.write_bytes(b'\xff')
        with self.assertRaisesRegex(ProjectFormatError, 'UTF-8'):
            load_project(self.path)
        self.path.write_bytes(b' ' * 1_048_577)
        with self.assertRaisesRegex(ProjectFormatError, 'bytes'):
            load_project(self.path)
        with self.assertRaises(FileNotFoundError):
            load_project(self.path.with_name('missing'))


if __name__ == '__main__':
    unittest.main()
