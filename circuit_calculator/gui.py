"""Tk junction-based DC editor. Tk is imported only when the GUI is launched."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
import math

from circuit_calculator.circuit import Circuit, CurrentSource, Resistor, VoltageSource
from circuit_calculator.circuit_io import CircuitDocument, load_document, save_document
from circuit_calculator.schematic import (EditorSession, Position, Schematic, Wire, component,
                       divider_example, terminals, value_of)


class CircuitEditor:
    def __init__(self, root, state=None):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.root = tk, ttk, root
        self.session = EditorSession(state or Schematic.from_document(CircuitDocument(Circuit(('n1',), ()))))
        self.mode, self.pending, self.selected = 'select', None, None
        self.drag_node = None
        self.zoom = 1.0
        self.dirty = False
        self.future = None
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='circuit-dc')
        self.closed = False
        root.title('Circuit Calculator — DC network editor')
        root.geometry('1180x760')
        root.minsize(900, 600)
        root.protocol('WM_DELETE_WINDOW', self.close)
        header = ttk.Frame(root, padding=(14, 10))
        header.pack(fill='x')
        ttk.Label(header, text='Circuit Calculator', font=('Segoe UI', 17, 'bold')).pack(side='left')
        ttk.Label(header, text='DC network editor', foreground='#526477').pack(side='left', padx=18)
        actions = ttk.Frame(root, padding=(10, 0, 10, 8))
        actions.pack(fill='x')
        self.buttons = {}
        for label, command in (('New', self.new), ('Example', self.example),
                               ('Open circuit', self.open), ('Export circuit', self.export),
                               ('Undo', self.undo), ('Redo', self.redo),
                               ('Edit value', self.edit_value), ('Delete', self.delete),
                               ('Simulate DC', self.simulate)):
            button = ttk.Button(actions, text=label, command=command)
            button.pack(side='left', padx=2)
            self.buttons[label] = button
        tools = ttk.Frame(root, padding=(10, 0, 10, 8))
        tools.pack(fill='x')
        self.tool = tk.StringVar(value='select')
        for label, mode in (('Select / move', 'select'), ('Junction', 'node'),
                            ('Resistor', 'resistor'), ('Voltage source', 'voltage'),
                            ('Current source', 'current'), ('Wire', 'wire'), ('Reference', 'ground')):
            ttk.Radiobutton(tools, text=label, variable=self.tool, value=mode,
                            command=self.change_mode).pack(side='left', padx=5)
        ttk.Button(tools, text='−', width=3, command=lambda: self.change_zoom(.8)).pack(side='right')
        ttk.Button(tools, text='+', width=3, command=lambda: self.change_zoom(1.25)).pack(side='right')
        self.status = tk.StringVar(value='Choose Junction to place nodes, then connect two nodes with a component.')
        ttk.Label(root, textvariable=self.status, padding=(14, 7), wraplength=1100).pack(fill='x')
        body = ttk.Panedwindow(root, orient='horizontal')
        body.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        drawing = ttk.Frame(body)
        body.add(drawing, weight=4)
        self.canvas = tk.Canvas(drawing, bg='#f6f9fc', highlightthickness=1,
                                highlightbackground='#ccd7e2', scrollregion=(-500, -500, 3000, 3000))
        xscroll = ttk.Scrollbar(drawing, orient='horizontal', command=self.canvas.xview)
        yscroll = ttk.Scrollbar(drawing, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        drawing.rowconfigure(0, weight=1)
        drawing.columnconfigure(0, weight=1)
        panel = ttk.Frame(body, padding=(12, 4))
        body.add(panel, weight=1)
        ttk.Label(panel, text='DC results', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        self.results = tk.Text(panel, width=34, wrap='word', relief='flat', bg='white',
                               padx=10, pady=10, state='disabled', font=('Consolas', 10))
        self.results.pack(fill='both', expand=True, pady=8)
        ttk.Label(root, text='Connect explicit junctions. Crossings and proximity do not connect. '
                  'Circuit exports preserve electrical connections; layout resets on reopen.',
                  padding=(14, 6), foreground='#526477', wraplength=1100).pack(fill='x')
        self.canvas.bind('<Button-1>', self.click)
        self.canvas.bind('<B1-Motion>', self.motion)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Double-Button-1>', lambda event: self.edit_value())
        self.canvas.bind('<ButtonPress-2>', lambda event: self.canvas.scan_mark(event.x, event.y))
        self.canvas.bind('<B2-Motion>', lambda event: self.canvas.scan_dragto(event.x, event.y, gain=1))
        root.bind('<Escape>', lambda event: self.cancel())
        root.bind('<Control-z>', lambda event: self.undo())
        root.bind('<Control-y>', lambda event: self.redo())
        root.bind('<F5>', lambda event: self.simulate())
        self.draw()

    def _text(self, text):
        self.results.configure(state='normal')
        self.results.delete('1.0', 'end')
        self.results.insert('1.0', text)
        self.results.configure(state='disabled')

    def change_mode(self):
        self.mode = self.tool.get()
        self.pending = None
        self.status.set('Click empty space to place a junction.' if self.mode == 'node' else
                        'Select a junction for the zero-volt reference.' if self.mode == 'ground' else
                        'Select and drag junctions; double-click a component to edit its value.' if self.mode == 'select' else
                        'Click two junctions in order. First is + / from / node_a; second is − / to / node_b.')
        self.draw()

    def cancel(self):
        self.pending = None
        self.tool.set('select')
        self.change_mode()

    def _apply(self, state):
        previous = self.session.revision
        self.session.apply(state)
        if previous != self.session.revision:
            self.dirty = True
            self._text('Results cleared after edit.\nRun Simulate DC to analyze the current circuit.')
        self.draw()

    def _error(self, error):
        self.status.set(str(error))

    def _next_name(self, prefix, used):
        i = 1
        while f'{prefix}{i}' in used:
            i += 1
        return f'{prefix}{i}'

    def _hit(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        items = self.canvas.find_overlapping(x - 6, y - 6, x + 6, y + 6)
        hits = []
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith('entity:'):
                    _, kind, name = tag.split(':', 2)
                    hits.append((kind, name))
        return next((hit for hit in hits if hit[0] == 'node'), hits[0] if hits else None)

    def click(self, event):
        hit = self._hit(event)
        try:
            if self.mode == 'node':
                if hit:
                    self.status.set('Choose empty space; proximity never merges junctions.')
                    return
                name = self._next_name('n', self.session.state.document.circuit.nodes)
                x = round(self.canvas.canvasx(event.x) / self.zoom / 20) * 20
                y = round(self.canvas.canvasy(event.y) / self.zoom / 20) * 20
                self._apply(self.session.state.add_node(name, x, y))
                self.status.set(f'Added junction {name}.')
            elif self.mode == 'select':
                self.selected = hit
                self.drag_node = hit[1] if hit and hit[0] == 'node' else None
                self.draw()
            elif hit and hit[0] == 'node':
                name = hit[1]
                if self.mode == 'ground':
                    self._apply(self.session.state.set_reference(name))
                    self.status.set(f'Reference junction: {name}.')
                elif self.pending is None:
                    self.pending = name
                    self.status.set(f'First terminal: {name}. Choose the second junction.')
                    self.draw()
                else:
                    first, self.pending = self.pending, None
                    if self.mode == 'wire':
                        wire_name = self._next_name('W', {w.name for w in self.session.state.wires})
                        self._apply(self.session.state.add_wire(Wire(wire_name, first, name)))
                    else:
                        self._create_component(first, name)
            else:
                self.status.set('Choose an explicit junction dot; wire crossings are not junctions.')
        except (ValueError, TypeError, InvalidOperation) as error:
            self.pending = None
            self._error(error)
        self.draw()

    def _create_component(self, first, second):
        from tkinter import simpledialog
        prefix = {'resistor': 'R', 'voltage': 'V', 'current': 'I'}[self.mode]
        used = {e.name for e in self.session.state.document.circuit.elements}
        name = simpledialog.askstring('Component', 'Name:', initialvalue=self._next_name(prefix, used), parent=self.root)
        if name is None:
            return
        unit = {'resistor': 'ohms', 'voltage': 'volts (+ to −)', 'current': 'amperes (from to)'}[self.mode]
        value = simpledialog.askstring('Component', f'Value in {unit}:', initialvalue='1000' if self.mode == 'resistor' else '1', parent=self.root)
        if value is None:
            return
        self._apply(self.session.state.add_element(component(self.mode, name, first, second, Decimal(value))))
        self.status.set(f'Added {name}: {first} → {second}.')

    def motion(self, event):
        if self.drag_node:
            try:
                position = Position(self.drag_node, round(self.canvas.canvasx(event.x) / self.zoom / 20) * 20,
                                    round(self.canvas.canvasy(event.y) / self.zoom / 20) * 20)
                self.draw(preview=position)
            except (ValueError, TypeError) as error:
                self._error(error)
                self.draw()

    def release(self, event):
        if self.drag_node:
            name, self.drag_node = self.drag_node, None
            try:
                self._apply(self.session.state.move_node(name,
                    round(self.canvas.canvasx(event.x) / self.zoom / 20) * 20,
                    round(self.canvas.canvasy(event.y) / self.zoom / 20) * 20))
            except (ValueError, TypeError) as error:
                self._error(error)
                self.draw()

    def draw(self, preview=None):
        canvas, state = self.canvas, self.session.state
        canvas.delete('all')
        positions = {p.node: (p.x * self.zoom, p.y * self.zoom) for p in state.positions}
        if preview:
            positions[preview.node] = (preview.x * self.zoom, preview.y * self.zoom)
        # Grid dots are decorative; only entity-tagged dots are electrical nodes.
        for x in range(0, 1600, 40):
            for y in range(0, 1200, 40):
                canvas.create_oval(x * self.zoom, y * self.zoom, x * self.zoom + 1, y * self.zoom + 1,
                                   fill='#dce5ee', outline='')
        for wire in state.wires:
            color = '#b25b10' if self.selected == ('wire', wire.name) else '#448269'
            canvas.create_line(*positions[wire.first], *positions[wire.second], fill=color,
                                width=3, tags=(f'entity:wire:{wire.name}',))
        pairs = {}
        for element in state.document.circuit.elements:
            a, b = terminals(element)
            pair = frozenset((a, b))
            index = pairs.get(pair, 0)
            pairs[pair] = index + 1
            x1, y1 = positions[a]
            x2, y2 = positions[b]
            length = math.hypot(x2 - x1, y2 - y1)
            ux, uy = ((x2 - x1) / length, (y2 - y1) / length) if length else (1, 0)
            px, py = -uy, ux
            offset = index * 48 * self.zoom
            cx, cy = (x1 + x2) / 2 + px * offset, (y1 + y2) / 2 + py * offset
            radius = 21 * self.zoom
            start, end = (cx - ux * radius, cy - uy * radius), (cx + ux * radius, cy + uy * radius)
            tag = (f'entity:element:{element.name}',)
            color = '#b25b10' if self.selected == ('element', element.name) else '#254e79'
            canvas.create_line(x1, y1, *start, fill=color, width=2, tags=tag)
            canvas.create_line(*end, x2, y2, fill=color, width=2, tags=tag)
            if type(element) is Resistor:
                points = []
                for i in range(9):
                    along = -radius + 2 * radius * i / 8
                    across = (6 * self.zoom * (-1 if i % 2 else 1)) if i not in (0, 8) else 0
                    points.extend((cx + ux * along + px * across, cy + uy * along + py * across))
                canvas.create_line(*points, fill=color, width=2, tags=tag)
                unit = 'Ω'
            else:
                canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                    outline=color, width=2, fill='#f6f9fc', tags=tag)
                if type(element) is VoltageSource:
                    for distance, label in ((-9, '+'), (9, '−')):
                        canvas.create_text(cx + ux * distance * self.zoom, cy + uy * distance * self.zoom,
                                            text=label, fill=color, tags=tag)
                    unit = 'V'
                else:
                    canvas.create_line(cx - ux * 11 * self.zoom, cy - uy * 11 * self.zoom,
                                        cx + ux * 11 * self.zoom, cy + uy * 11 * self.zoom,
                                        arrow='last', fill=color, width=2, tags=tag)
                    unit = 'A'
            canvas.create_text(cx + px * 38 * self.zoom, cy + py * 38 * self.zoom,
                                text=f'{element.name}  {value_of(element):g} {unit}\n{a} → {b}',
                                anchor=('e' if px < 0 else 'w') if abs(px) > .6 else ('s' if py < 0 else 'n'),
                                fill=color, font=('Segoe UI', 9), tags=tag)
        for node, (x, y) in positions.items():
            tag = (f'entity:node:{node}',)
            selected = self.selected == ('node', node) or self.pending == node
            color = '#b25b10' if selected else '#173b61'
            canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill=color, outline='white', width=2, tags=tag)
            canvas.create_text(x + 12, y - 13, text=node, anchor='w', fill=color,
                                font=('Segoe UI', 10, 'bold'), tags=tag)
            if state.document.circuit.reference_node == node:
                canvas.create_line(x, y + 7, x, y + 18, fill=color, width=2, tags=tag)
                for width, dy in ((14, 18), (9, 23), (4, 28)):
                    canvas.create_line(x - width, y + dy, x + width, y + dy, fill=color, width=2, tags=tag)
        canvas.configure(scrollregion=canvas.bbox('all') or (0, 0, 1000, 700))

    def change_zoom(self, factor):
        self.zoom = min(2.5, max(.4, self.zoom * factor))
        self.draw()

    def undo(self):
        before = self.session.revision
        self.session.undo()
        self._history_changed(before)

    def redo(self):
        before = self.session.revision
        self.session.redo()
        self._history_changed(before)

    def _history_changed(self, before):
        if self.session.revision != before:
            self.dirty = True
            self.selected = self.pending = None
            self._text('Results cleared after Undo/Redo. Run Simulate DC again.')
            self.draw()

    def edit_value(self):
        from tkinter import simpledialog
        if not self.selected or self.selected[0] != 'element':
            self.status.set('Select a component to edit its value.')
            return
        element = next((e for e in self.session.state.document.circuit.elements if e.name == self.selected[1]), None)
        if element is None:
            return
        text = simpledialog.askstring('Edit value', 'Value in base SI units:', initialvalue=str(value_of(element)), parent=self.root)
        if text is not None:
            try:
                self._apply(self.session.state.change_value(element.name, Decimal(text)))
            except (TypeError, ValueError, InvalidOperation) as error:
                self._error(error)

    def delete(self):
        if self.selected:
            try:
                state = self.session.state.delete(*self.selected)
                self.selected = self.pending = None
                self._apply(state)
            except (ValueError, TypeError) as error:
                self._error(error)

    def _discard(self):
        from tkinter import messagebox
        return not self.dirty or messagebox.askyesno('Discard edits?',
            'Discard the current unsaved editor changes?', parent=self.root)

    def new(self):
        if self._discard():
            self._apply(Schematic.from_document(CircuitDocument(Circuit(('n1',), ()))))
            self.selected = self.pending = None

    def example(self):
        if self._discard():
            self._apply(divider_example())
            self.selected = self.pending = None
            self.status.set('Example: select Simulate DC. Expected output at out: 8 V.')

    def open(self):
        from tkinter import filedialog
        if not self._discard():
            return
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('Circuit JSON', '*.json')])
        if path:
            try:
                state = Schematic.from_document(load_document(path))
                self._apply(state)
                self.selected = self.pending = None
                self.dirty = False
                self.status.set('Opened electrical circuit. Junction positions were arranged automatically.')
            except (ValueError, TypeError, OSError) as error:
                self._error(error)

    def export(self):
        from tkinter import filedialog, messagebox
        try:
            document = self.session.state.compile()
            path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json',
                                               filetypes=[('Electrical circuit JSON — layout not saved', '*.json')],
                                               confirmoverwrite=False)
            if not path:
                return
            try:
                save_document(document, path)
            except FileExistsError:
                if not messagebox.askyesno('Replace circuit file?',
                    'Replace this file? Only electrical connectivity is exported; layout is not saved.', parent=self.root):
                    return
                save_document(document, path, overwrite=True)
            self.status.set('Electrical circuit exported. Layout is not saved; reopening arranges junctions automatically.')
            # Layout and wire segmentation are still unsaved editor work.
        except (ValueError, TypeError, OSError) as error:
            self._error(error)

    def simulate(self):
        if self.future is not None:
            return
        try:
            circuit = self.session.state.compile().circuit
            unknowns = len(circuit.nodes) - (circuit.reference_node is not None)
            unknowns += sum(type(e) is VoltageSource for e in circuit.elements)
            if unknowns > 200:
                raise ValueError('GUI DC limit: 200 unknowns')
            from circuit_calculator.dc import solve_dc
            self.session.result = None
            self._text('Solving DC circuit…')
            self.submitted_revision = self.session.revision
            self.future = self.worker.submit(solve_dc, circuit)
            self.buttons['Simulate DC'].configure(state='disabled')
            self.root.after(40, self._poll)
        except (ValueError, TypeError) as error:
            self._text('No current simulation result.')
            self._error(error)

    def _poll(self):
        if self.closed:
            return
        if not self.future.done():
            self.root.after(40, self._poll)
            return
        future, self.future = self.future, None
        self.buttons['Simulate DC'].configure(state='normal')
        try:
            result = future.result()
            if not self.session.accept_result(self.submitted_revision, result):
                self.status.set('Circuit changed while solving. Run Simulate DC again.')
                return
            mapping = self.session.state.net_names()
            lines = ['Node voltages (V)']
            lines += [f'{node}: {result.node_voltages[net]:.9g}' for node, net in mapping.items()]
            lines += ['', 'Components (V, A, W)']
            for name, value in result.elements.items():
                lines += [name, f'  V {value.voltage_volts:.9g}', f'  I {value.current_amperes:.9g}',
                          f'  P {value.power_watts:.9g}']
            lines += ['', 'Positive power: absorbed', 'Negative power: delivered',
                      f'KCL residual: {result.max_kcl_residual_amperes:.3g} A',
                      f'Power balance: {result.power_balance_watts:.3g} W']
            self._text('\n'.join(lines))
            self.status.set('DC solved. Results follow each component’s displayed terminal order.')
        except (ValueError, TypeError, ImportError) as error:
            if self.submitted_revision == self.session.revision:
                self._text('No current simulation result.')
                self._error(error)
        except Exception as error:
            self._text('Simulation failed unexpectedly; no result is available.')
            self._error(f'Internal simulation error: {type(error).__name__}: {error}')

    def close(self):
        if self._discard():
            self.closed = True
            self.worker.shutdown(wait=False, cancel_futures=True)
            self.root.destroy()


def launch(state=None):
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise ValueError('Cannot initialize a Tk display; run the GUI in a desktop session with Tcl/Tk installed') from error
    CircuitEditor(root, state)
    root.mainloop()
