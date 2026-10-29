"""Shared main-thread Tk lifecycle and workflow helpers."""

import gc
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tkinter as tk
from circuit_calculator.gui import CircuitEditor
from circuit_calculator.schematic import Wire, Waypoint, Position, Schematic, divider_example
from circuit_calculator.circuit import Circuit
from circuit_calculator.circuit_io import CircuitDocument


REPO_ROOT = Path(__file__).resolve().parents[2]


class WorkflowCase(unittest.TestCase):
    def drive_find(self, action):
        self.drive_dialog('Find item', action)

    def select_component(self, name):
        position = self.app.session.state.component_placement(name)
        point = self.point(position.x, position.y)
        self.app.click(point)
        self.app.release(point)
        self.assertEqual(self.app.selected, ('element', name))

    def inspection_text(self):
        return self.app.inspection.get('1.0', 'end')

    def send_shortcut(self, widget, key, windows_code, state=4):
        if widget is self.app.results:
            self.app.result_tabs.select(self.app.all_results_tab)
        elif widget is self.app.inspection:
            self.app.result_tabs.select(self.app.inspection_tab)
        self.root.deiconify()
        self.root.update()
        widget.focus_force()
        self.root.update()
        self.assertIs(self.root.focus_get(), widget)
        identity = {'keycode': windows_code} if sys.platform == 'win32' else {'keysym': key}
        widget.event_generate('<KeyPress>', state=state, when='tail', **identity)
        self.root.update()

    def drive_details(self, action):
        self.drive_dialog('Project details', action)

    def drive_dialog(self, title, action):
        """Exercise the real modal form with a bounded cleanup on assertion failure."""
        self.root.deiconify()
        self.root.update()
        failures = []
        def dialog():
            candidates = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)
                          and w.title() == title]
            self.assertEqual(len(candidates), 1)
            return candidates[0]
        def respond():
            try:
                action(dialog())
            except BaseException as error:
                failures.append(error)
                for child in self.root.winfo_children():
                    if isinstance(child, tk.Toplevel):
                        child.cancel()
        def timeout():
            failures.append(AssertionError(title + ' dialog did not finish in five seconds'))
            for child in self.root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.cancel()
        timer = self.root.after(5000, timeout)
        self.root.after(80, respond)
        try:
            self.app.buttons[title].invoke()
        finally:
            self.root.after_cancel(timer)
        if failures:
            raise failures[0]

    def settle_viewport(self):
        self.root.deiconify()
        self.root.update()
        self.root.update_idletasks()
        self.app._ensure_viewport()

    def world_center(self):
        canvas = self.app.canvas
        return (canvas.canvasx(canvas.winfo_width() / 2) / self.app.zoom,
                canvas.canvasy(canvas.winfo_height() / 2) / self.app.zoom)

    def bend_wire(self, name='W1'):
        self.app._apply(self.app.session.state.route_wire('W1', (Waypoint(500, 500), Waypoint(160, 500))))
        if name != 'W1':
            from dataclasses import replace
            state = self.app.session.state
            self.app._apply(replace(state, wires=tuple(replace(w, name=name) if w.name == 'W1' else w for w in state.wires)))
        self.mode('select')
        self.app.selected = ('wire', name)
        self.app.draw()

    def angle_document(self):
        self.app._reset_document(Schematic(CircuitDocument(Circuit(('a', 'b', 'unconnected'), (), 'a')),
            (Position('a', 100, 100), Position('b', 300, 300), Position('unconnected', 300, 100))))
        self.app.orthogonal.set(True)
        self.app.routing_style_changed()
        self.mode('wire')

    def crossing(self):
        self.app._reset_document(Schematic(CircuitDocument(Circuit(('a', 'b', 'c', 'd'), (), 'a')),
            (Position('a', 100, 300), Position('b', 500, 300), Position('c', 300, 100), Position('d', 300, 500)),
            (Wire('H', 'a', 'b'), Wire('V', 'c', 'd'))))

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = CircuitEditor(self.root, divider_example())
        self.root.update_idletasks()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if not self.app.closed:
            self.app.closed = True
            self.app.worker.shutdown(wait=True, cancel_futures=True)
            self.root.destroy()
        # Dispose all prior Tk cycles on their owning thread, before a later
        # NumPy worker allocation can trigger cyclic GC on another thread.
        del self.app, self.root
        gc.collect()

    def point(self, x, y):
        canvas = self.app.canvas
        return SimpleNamespace(x=x * self.app.zoom - canvas.canvasx(0),
                               y=y * self.app.zoom - canvas.canvasy(0))

    def node(self, name):
        p = next(p for p in self.app.session.state.positions if p.node == name)
        return self.point(p.x, p.y)

    def mode(self, mode):
        self.app.tool.set(mode)
        self.app.change_mode()

    def project_path(self):
        scratch = REPO_ROOT / '.build-check'
        scratch.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name) / 'test.ccproj.json'

    def wait_for_result(self):
        deadline = time.monotonic() + 5
        while self.app.future is not None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertIsNone(self.app.future, 'GUI solve did not complete in five seconds')

    def place_resistor(self):
        self.mode('resistor')
        with patch('tkinter.simpledialog.askstring', side_effect=['R3', '3000']):
            self.app.click(self.point(800, 300))
        self.mode('select')
        return self.app.session.state.document.circuit.elements[-1]
