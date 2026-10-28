"""Tk schematic DC editor. Tk is imported only when the GUI is launched."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
import math
from pathlib import Path

from circuit_calculator.circuit import Circuit, CurrentSource, Resistor, VoltageSource
from circuit_calculator.circuit_io import CircuitDocument, load_document, save_document
from circuit_calculator.schematic import (EditorSession, Position, Schematic, Wire, Waypoint, MAX_BENDS,
                       component, divider_example, terminals, value_of, orthogonal_bends)
from circuit_calculator.project_io import (SchematicProject, ViewState, load_project,
                                          save_project as write_project)


class CircuitEditor:
    def __init__(self, root, state=None, *, project=None, project_path=None):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.root = tk, ttk, root
        if project is not None and state is not None:
            raise TypeError('Choose state or project, not both')
        self.session = EditorSession(project.schematic if project is not None else
                                     state or Schematic.from_document(CircuitDocument(Circuit(('n1',), ()))))
        self.project_path = Path(project_path).resolve() if project_path is not None else None
        self.mode, self.pending, self.selected = 'select', None, None
        self.route_bends, self.routing_wire = [], None
        self.drag_node = None
        self.drag_element = None
        self.drag_bend = self.selected_bend = None
        self.drag_offset = (0, 0)
        self.drag_origin = (0, 0)
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
        edit_actions = ttk.Frame(root, padding=(10, 0, 10, 8))
        edit_actions.pack(fill='x')
        self.buttons = {}
        for label, command in (('New', self.new), ('Example', self.example),
                               ('Open Project', self.open_project), ('Save Project', self.save_project),
                               ('Save As', self.save_project_as), ('Import circuit', self.open),
                               ('Export circuit', self.export),
                               ('Undo', self.undo), ('Redo', self.redo),
                               ('Edit value', self.edit_value), ('Rotate 90°', self.rotate), ('Delete', self.delete),
                               ('Reroute wire', self.reroute_wire), ('Straighten', self.straighten_wire),
                               ('Orthogonalize', self.orthogonalize),
                               ('Simulate DC', self.simulate)):
            parent = edit_actions if label in ('Undo', 'Redo', 'Edit value', 'Rotate 90°', 'Delete', 'Reroute wire', 'Straighten', 'Orthogonalize', 'Simulate DC') else actions
            button = ttk.Button(parent, text=label, command=command)
            button.pack(side='left', padx=2)
            self.buttons[label] = button
        self.orthogonal = tk.BooleanVar(value=False)
        self.horizontal_first = True
        ttk.Checkbutton(actions, text='Right-angle wires', variable=self.orthogonal,
                        command=self.routing_style_changed).pack(side='right', padx=8)
        tools = ttk.Frame(root, padding=(10, 0, 10, 8))
        tools.pack(fill='x')
        self.tool = tk.StringVar(value='select')
        for label, mode in (('Select / move', 'select'), ('Junction', 'node'),
                            ('Resistor', 'resistor'), ('Voltage source', 'voltage'),
                            ('Current source', 'current'), ('Wire', 'wire'), ('Split wire', 'split'), ('Reference', 'ground')):
            ttk.Radiobutton(tools, text=label, variable=self.tool, value=mode,
                            command=self.change_mode).pack(side='left', padx=5)
        ttk.Button(tools, text='−', width=3, command=lambda: self.change_zoom(.8)).pack(side='right')
        ttk.Button(tools, text='+', width=3, command=lambda: self.change_zoom(1.25)).pack(side='right')
        self.status = tk.StringVar(value='Choose a component tool, click empty space, then connect its terminal dots with Wire.')
        ttk.Label(root, textvariable=self.status, padding=(14, 7), wraplength=1100).pack(fill='x')
        body = ttk.Panedwindow(root, orient='horizontal')
        body.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        drawing = ttk.Frame(body)
        body.add(drawing, weight=4)
        self.canvas = tk.Canvas(drawing, bg='#f6f9fc', highlightthickness=1,
                                highlightbackground='#ccd7e2', scrollregion=(-500, -500, 3000, 3000))
        xscroll = ttk.Scrollbar(drawing, orient='horizontal', command=lambda *args: self._scroll('x', *args))
        yscroll = ttk.Scrollbar(drawing, orient='vertical', command=lambda *args: self._scroll('y', *args))
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
        ttk.Label(root, text='Wire terminal dots or junctions explicitly. Crossings and proximity do not connect. '
                  'Project saves include layout; circuit exports contain electrical connections only.',
                  padding=(14, 6), foreground='#526477', wraplength=1100).pack(fill='x')
        self.canvas.bind('<Button-1>', self.click)
        self.canvas.bind('<B1-Motion>', self.motion)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Shift-Button-1>', self.insert_bend_at)
        self.canvas.bind('<Double-Button-1>', lambda event: self.edit_value())
        self.canvas.bind('<Key-r>', lambda event: self.rotate())
        self.canvas.bind('<Key-R>', lambda event: self.rotate())
        self.canvas.bind('<BackSpace>', lambda event: self.remove_bend())
        self.canvas.bind('<Delete>', lambda event: self.delete())
        self.canvas.bind('<space>', self.toggle_route_order)
        self.canvas.bind('<Motion>', self.route_motion)
        self.canvas.bind('<ButtonPress-2>', lambda event: self.canvas.scan_mark(event.x, event.y))
        self.canvas.bind('<B2-Motion>', self._pan)
        root.bind('<Escape>', lambda event: self.cancel())
        root.bind('<Control-z>', lambda event: self.undo())
        root.bind('<Control-y>', lambda event: self.redo())
        root.bind('<F5>', lambda event: self.simulate())
        root.bind('<Control-s>', lambda event: self.save_project())
        root.bind('<Control-Shift-S>', lambda event: self.save_project_as())
        root.bind('<Control-o>', lambda event: self.open_project())
        self.draw()
        self.root.update_idletasks()
        if project is not None:
            self._restore_view(project.view)
        self._clean_project = self._snapshot()
        self._update_dirty()

    def _snapshot(self):
        return SchematicProject(self.session.state,
                                ViewState(self.zoom, self.canvas.xview()[0], self.canvas.yview()[0]))

    def _restore_view(self, view):
        self.zoom = view.zoom
        self.draw()
        self.root.update_idletasks()
        self.canvas.xview_moveto(view.scroll_x)
        self.canvas.yview_moveto(view.scroll_y)

    def _update_dirty(self):
        self.dirty = self._snapshot() != self._clean_project
        name = self.project_path.name if self.project_path is not None else 'Untitled'
        self.root.title(f'Circuit Calculator — {name}{" *" if self.dirty else ""}')

    def _scroll(self, axis, *args):
        getattr(self.canvas, axis + 'view')(*args)
        self._update_dirty()

    def _pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self._update_dirty()

    def _text(self, text):
        self.results.configure(state='normal')
        self.results.delete('1.0', 'end')
        self.results.insert('1.0', text)
        self.results.configure(state='disabled')

    def change_mode(self):
        self.mode = self.tool.get()
        self._clear_route()
        self.drag_node = self.drag_element = self.drag_bend = self.selected_bend = None
        self.status.set('Click empty space to place a junction.' if self.mode == 'node' else
                        'Select a terminal or junction for the zero-volt reference.' if self.mode == 'ground' else
                        'Drag a body, junction or selected wire bend. Shift-click a selected wire to add a bend; Delete removes a selected bend.' if self.mode == 'select' else
                        'Click a dot, empty space for bends, then another dot. Esc cancels; Backspace removes a bend.' if self.mode == 'wire' else
                        'Click a wire segment to split it. At overlaps, select the intended wire first.' if self.mode == 'split' else
                        'Click empty space to place a component, or select two free junctions in terminal order.')
        self.draw()

    def cancel(self):
        self.pending = None
        self.tool.set('select')
        self.change_mode()

    def _apply(self, state):
        previous = self.session.revision
        self.session.apply(state)
        if previous != self.session.revision:
            self._clear_route()
            self._text('Results cleared after edit.\nRun Simulate DC to analyze the current circuit.')
        self.draw()
        self._update_dirty()

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
                    if kind == 'bend':
                        index = next(t.split(':', 1)[1] for t in tags if t.startswith('bend-index:'))
                        hits.append((kind, (name, int(index))))
                        continue
                    hits.append((kind, name))
        bend = next((hit for hit in hits if hit[0] == 'bend'), None)
        if bend is not None:
            return bend
        return next((hit for hit in hits if hit[0] in ('node', 'terminal')), hits[0] if hits else None)

    def _clear_route(self):
        self.pending, self.routing_wire = None, None
        self.route_bends = []

    def route_motion(self, event):
        if self.mode == 'wire' and self.pending is not None:
            self._preview_route(event)

    def _preview_route(self, event=None):
        self.canvas.delete('route-preview')
        if self.mode != 'wire' or self.pending is None:
            return
        start = next((p for p in self.session.state.positions if p.node == self.pending), None)
        if start is None:
            return
        points = [(start.x, start.y)]
        points += [(p.x, p.y) for p in self.route_bends]
        if event is not None:
            points.append((self.canvas.canvasx(event.x) / self.zoom, self.canvas.canvasy(event.y) / self.zoom))
        if len(points) > 1:
            if self.orthogonal.get():
                try:
                    bends = orthogonal_bends(points, horizontal_first=self.horizontal_first)
                    points = [points[0], *((p.x, p.y) for p in bends), points[-1]]
                except (ValueError, TypeError):
                    return
            self.canvas.create_line(*(v * self.zoom for point in points for v in point), fill='#b25b10',
                                    width=2, dash=(5, 4), tags=('route-preview',))

    def routing_style_changed(self):
        self._preview_route()
        self.status.set('Right-angle routing enabled. Space swaps elbow order while drawing.' if self.orthogonal.get() else
                        'Free-path routing enabled.')

    def toggle_route_order(self, event=None):
        if self.mode == 'wire' and self.pending is not None and self.orthogonal.get():
            self.horizontal_first = not self.horizontal_first
            self._preview_route()
            self.status.set(('Horizontal' if self.horizontal_first else 'Vertical') + '-first right-angle routing. Space swaps order.')
        return 'break'

    def _completed_bends(self, first, second):
        if not self.orthogonal.get():
            return tuple(self.route_bends)
        positions = {p.node: (p.x, p.y) for p in self.session.state.positions}
        return orthogonal_bends((positions[first], *((p.x, p.y) for p in self.route_bends), positions[second]),
                                horizontal_first=self.horizontal_first)

    def orthogonalize(self):
        if not self.selected or self.selected[0] != 'wire':
            self.status.set('Select a wire to convert to right angles.')
            return
        try:
            state = self.session.state.orthogonalize_wire(self.selected[1], horizontal_first=self.horizontal_first)
            self.selected_bend = None
            self._apply(state)
            self.status.set('Converted selected wire to right angles; endpoints and connections are unchanged.')
        except (ValueError, TypeError) as error:
            self._error(error)

    def insert_bend_at(self, event):
        self.canvas.focus_set()
        if self.mode != 'select' or not self.selected or self.selected[0] != 'wire':
            self.status.set('Select a wire, then Shift-click the interior of its segment to add a bend.')
            return 'break'
        try:
            name = self.selected[1]
            x, y = self.canvas.canvasx(event.x) / self.zoom, self.canvas.canvasy(event.y) / self.zoom
            segment, point, distance = self.session.state.nearest_wire_segment(name, x, y)
            if distance * self.zoom > 6:
                raise ValueError('Shift-click the selected wire segment')
            state = self.session.state.insert_wire_bend(name, segment, *point)
            self.selected_bend = (name, segment)
            self._apply(state)
            self.status.set('Bend inserted. Drag its square handle; Delete removes the selected bend.')
        except (ValueError, TypeError) as error:
            self._error(error)
        return 'break'

    def remove_bend(self):
        if self.mode == 'wire' and self.pending is not None and self.route_bends:
            self.route_bends.pop()
            self._preview_route()
            self.status.set('Last pending bend removed. Choose another bend or the ending dot.')

    def reroute_wire(self):
        if not self.selected or self.selected[0] != 'wire':
            self.status.set('Select a wire to reroute.')
            return
        wire = next((w for w in self.session.state.wires if w.name == self.selected[1]), None)
        if wire is None:
            return
        self.tool.set('wire')
        self.change_mode()
        self.pending, self.routing_wire = wire.first, wire.name
        self.status.set(f'Rerouting {wire.name}: add bends, then click {self.session.state.endpoint_label(wire.second)}. Esc cancels.')
        self.draw()

    def straighten_wire(self):
        if not self.selected or self.selected[0] != 'wire':
            self.status.set('Select a wire to straighten.')
            return
        try:
            state = self.session.state.route_wire(self.selected[1], ())
            self.selected_bend = None
            self._clear_route()
            self._apply(state)
            self.status.set('Wire bends removed; endpoint connections are unchanged.')
        except (ValueError, TypeError) as error:
            self._error(error)

    def split_at(self, event, hit):
        if hit and hit[0] == 'terminal':
            raise ValueError('Use Wire to connect a component terminal; split at a free junction or segment')
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        names = set()
        for item in self.canvas.find_overlapping(x - 6, y - 6, x + 6, y + 6):
            names.update(tag.split(':', 2)[2] for tag in self.canvas.gettags(item) if tag.startswith('entity:wire:'))
        chosen = self.selected[1] if self.selected and self.selected[0] == 'wire' and self.selected[1] in names else None
        if chosen is None:
            if len(names) != 1:
                raise ValueError('Select the intended wire away from the crossing, then use Split wire here' if names else
                                 'Choose a wire segment to split')
            chosen = next(iter(names))
        state = self.session.state
        junction = hit[1] if hit and hit[0] == 'node' else None
        if junction is not None:
            position = next(p for p in state.positions if p.node == junction)
            x, y = position.x, position.y
        else:
            x, y = x / self.zoom, y / self.zoom
        segment, point, distance = state.nearest_wire_segment(chosen, x, y)
        if distance * self.zoom > 6:
            raise ValueError('Choose a point on the intended wire segment')
        if junction is None:
            x, y = point
        result = state.split_wire(chosen, segment, x, y, junction=junction)
        junction = junction or result.document.circuit.nodes[-1]
        self.selected = ('node', junction)
        self._apply(result)
        self.status.set(f'Split {chosen} at junction {junction}. Only this wire was split; crossings stay separate until explicitly joined.')

    def click(self, event):
        self.canvas.focus_set()
        hit = self._hit(event)
        try:
            if self.mode == 'split':
                self.split_at(event, hit)
            elif self.mode == 'wire' and self.pending is not None and not hit:
                if len(self.route_bends) >= MAX_BENDS:
                    raise ValueError('Wire limit: at most 32 bends')
                self.route_bends.append(Waypoint(round(self.canvas.canvasx(event.x) / self.zoom / 20) * 20,
                                                round(self.canvas.canvasy(event.y) / self.zoom / 20) * 20))
                self.status.set('Bend added. Click empty space for another bend or an ending dot; crossings do not connect.')
            elif self.mode == 'node':
                if hit:
                    self.status.set('Choose empty space; proximity never merges junctions.')
                    return
                name = self._next_name('n', self.session.state.document.circuit.nodes)
                x = round(self.canvas.canvasx(event.x) / self.zoom / 20) * 20
                y = round(self.canvas.canvasy(event.y) / self.zoom / 20) * 20
                self._apply(self.session.state.add_node(name, x, y))
                self.status.set(f'Added junction {name}.')
            elif self.mode == 'select':
                self.drag_bend = self.selected_bend = None
                self.selected = hit
                self.drag_node = hit[1] if hit and hit[0] == 'node' else None
                self.drag_element = hit[1] if hit and hit[0] == 'element' else None
                if hit and hit[0] == 'bend':
                    name, index = hit[1]
                    self.selected = ('wire', name)
                    self.drag_bend = self.selected_bend = (name, index)
                    point = next(w for w in self.session.state.wires if w.name == name).bends[index]
                    self.drag_origin = (event.x, event.y)
                    self.drag_offset = (self.canvas.canvasx(event.x) / self.zoom - point.x,
                                        self.canvas.canvasy(event.y) / self.zoom - point.y)
                if self.drag_element:
                    placement = self.session.state.component_placement(self.drag_element)
                    self.drag_origin = (event.x, event.y)
                    self.drag_offset = (self.canvas.canvasx(event.x) / self.zoom - placement.x,
                                        self.canvas.canvasy(event.y) / self.zoom - placement.y)
                self.draw()
            elif self.mode in ('resistor', 'voltage', 'current') and not hit:
                self.pending = None
                self._create_component(None, None, position=(
                    round(self.canvas.canvasx(event.x) / self.zoom / 20) * 20,
                    round(self.canvas.canvasy(event.y) / self.zoom / 20) * 20))
            elif hit and hit[0] in ('node', 'terminal'):
                name = hit[1]
                if self.mode == 'ground':
                    self._apply(self.session.state.set_reference(name))
                    self.status.set(f'Reference: {self.session.state.endpoint_label(name)}.')
                elif hit[0] == 'terminal' and self.mode != 'wire':
                    self.pending = None
                    self.status.set('Use Wire to connect an existing component terminal.')
                elif self.pending is None:
                    self.pending = name
                    self.status.set(f'First endpoint: {self.session.state.endpoint_label(name)}. Choose another terminal or junction.')
                    self.draw()
                else:
                    first = self.pending
                    if self.mode == 'wire':
                        if self.routing_wire is not None:
                            wire = next(w for w in self.session.state.wires if w.name == self.routing_wire)
                            if name != wire.second:
                                raise ValueError('A rerouted wire must finish at its original ending dot')
                            state = self.session.state.route_wire(wire.name, self._completed_bends(first, name))
                        else:
                            wire_name = self._next_name('W', {w.name for w in self.session.state.wires})
                            state = self.session.state.add_wire(Wire(wire_name, first, name, self._completed_bends(first, name)))
                        self._clear_route()
                        self._apply(state)
                    else:
                        self.pending = None
                        self._create_component(first, name)
            else:
                self.status.set('Choose an explicit junction dot; wire crossings are not junctions.')
        except (ValueError, TypeError, InvalidOperation) as error:
            if self.mode != 'wire':
                self._clear_route()
            self._error(error)
        self.draw()

    def _create_component(self, first, second, *, position=None):
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
        if position is None:
            state = self.session.state.add_element(component(self.mode, name, first, second, Decimal(value)))
        else:
            state = self.session.state.add_placed_component(self.mode, name, *position, Decimal(value))
        self._apply(state)
        self.status.set(f'Added {name}. Use Wire to connect its terminal dots.')

    def _drag_position(self, event):
        return (round((self.canvas.canvasx(event.x) / self.zoom - self.drag_offset[0]) / 20) * 20,
                round((self.canvas.canvasy(event.y) / self.zoom - self.drag_offset[1]) / 20) * 20)

    def motion(self, event):
        if self.drag_bend is not None:
            try:
                self.draw(schematic=self.session.state.move_wire_bend(*self.drag_bend, *self._drag_position(event)))
            except (ValueError, TypeError) as error:
                self._error(error)
                self.draw()
        if self.drag_element:
            try:
                self.draw(schematic=self.session.state.move_component(self.drag_element, *self._drag_position(event)))
            except (ValueError, TypeError) as error:
                self._error(error)
                self.draw()
        if self.drag_node:
            try:
                position = Position(self.drag_node, round(self.canvas.canvasx(event.x) / self.zoom / 20) * 20,
                                    round(self.canvas.canvasy(event.y) / self.zoom / 20) * 20)
                self.draw(preview=position)
            except (ValueError, TypeError) as error:
                self._error(error)
                self.draw()

    def release(self, event):
        if self.drag_bend is not None:
            target, self.drag_bend = self.drag_bend, None
            try:
                distance = math.hypot(event.x - self.drag_origin[0], event.y - self.drag_origin[1])
                if distance > 3:
                    self._apply(self.session.state.move_wire_bend(*target, *self._drag_position(event)))
            except (ValueError, TypeError) as error:
                self._error(error)
            self.draw()
        if self.drag_element:
            name, self.drag_element = self.drag_element, None
            try:
                placement = self.session.state.component_placement(name)
                position = self._drag_position(event)
                distance = math.hypot(event.x - self.drag_origin[0], event.y - self.drag_origin[1])
                if distance > 3 and position != (placement.x, placement.y):
                    self._apply(self.session.state.move_component(name, *position))
            except (ValueError, TypeError) as error:
                self._error(error)
            self.draw()
        if self.drag_node:
            name, self.drag_node = self.drag_node, None
            try:
                self._apply(self.session.state.move_node(name,
                    round(self.canvas.canvasx(event.x) / self.zoom / 20) * 20,
                    round(self.canvas.canvasy(event.y) / self.zoom / 20) * 20))
            except (ValueError, TypeError) as error:
                self._error(error)
                self.draw()

    def draw(self, preview=None, *, schematic=None):
        canvas, state = self.canvas, schematic or self.session.state
        previous_region = canvas.cget('scrollregion')
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
            path = (positions[wire.first], *((p.x * self.zoom, p.y * self.zoom) for p in wire.bends), positions[wire.second])
            canvas.create_line(*(v for point in path for v in point), fill=color,
                                width=3, tags=(f'entity:wire:{wire.name}',))
        pairs = {}
        placed = {p.element: p for p in state.placements}
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
            if element.name in placed:
                placement = placed[element.name]
                cx, cy = placement.x * self.zoom, placement.y * self.zoom
                ux, uy = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[placement.rotation]
                px, py = -uy, ux
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
                                text=f'{element.name}  {value_of(element):g} {unit}\n{state.endpoint_label(a)} → {state.endpoint_label(b)}',
                                anchor=('e' if px < 0 else 'w') if abs(px) > .6 else ('s' if py < 0 else 'n'),
                                fill=color, font=('Segoe UI', 9), tags=tag)
        owners = state.terminal_owners()
        for node, (x, y) in positions.items():
            kind = 'terminal' if node in owners else 'node'
            tag = (f'entity:{kind}:{node}',)
            selected = self.selected == (kind, node) or self.pending == node
            color = '#b25b10' if selected else '#173b61'
            canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill=color, outline='white', width=2, tags=tag)
            canvas.create_text(x + 12, y - 13, text=state.endpoint_label(node), anchor='w', fill=color,
                                font=('Segoe UI', 10, 'bold'), tags=tag)
            if state.document.circuit.reference_node == node:
                canvas.create_line(x, y + 7, x, y + 18, fill=color, width=2, tags=tag)
                for width, dy in ((14, 18), (9, 23), (4, 28)):
                    canvas.create_line(x - width, y + dy, x + width, y + dy, fill=color, width=2, tags=tag)
        content_region = canvas.bbox('all') or (0, 0, 1000, 700)
        if self.mode == 'select' and self.selected and self.selected[0] == 'wire':
            wire = next((w for w in state.wires if w.name == self.selected[1]), None)
            if wire is not None:
                for index, point in enumerate(wire.bends):
                    x, y = point.x * self.zoom, point.y * self.zoom
                    fill = '#b25b10' if self.selected_bend == (wire.name, index) else 'white'
                    canvas.create_rectangle(x - 5, y - 5, x + 5, y + 5, fill=fill, outline='#b25b10', width=2,
                                            tags=(f'entity:bend:{wire.name}', f'bend-index:{index}'))
        canvas.configure(scrollregion=previous_region if preview is not None or schematic is not None else
                         content_region)
        self._preview_route()

    def change_zoom(self, factor):
        self.zoom = min(2.5, max(.4, self.zoom * factor))
        self.draw()
        self._update_dirty()

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
            self.selected = self.pending = None
            self._clear_route()
            self.drag_node = self.drag_element = None
            self.drag_bend = self.selected_bend = None
            self._text('Results cleared after Undo/Redo. Run Simulate DC again.')
            self.draw()
            self._update_dirty()

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

    def rotate(self):
        if not self.selected or self.selected[0] != 'element':
            self.status.set('Select a component body to rotate it.')
            return
        try:
            self._apply(self.session.state.rotate_component(self.selected[1]))
            self.status.set('Rotated 90° clockwise. Terminal identities and connections are preserved.')
        except (ValueError, TypeError) as error:
            self._error(error)

    def delete(self):
        if self.selected_bend is not None:
            try:
                state = self.session.state.remove_wire_bend(*self.selected_bend)
                self.drag_bend = self.selected_bend = None
                self._apply(state)
                self.status.set('Selected bend removed; the wire remains connected.')
            except (ValueError, TypeError) as error:
                self._error(error)
            return
        if self.selected:
            try:
                if self.selected[0] == 'terminal':
                    raise ValueError('Select the component body to delete it; terminals belong to the component')
                state = self.session.state.delete(*self.selected)
                self.selected = self.pending = None
                self._apply(state)
            except (ValueError, TypeError) as error:
                self._error(error)

    def _discard(self):
        from tkinter import messagebox
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel('Unsaved project',
            'Save project changes before continuing?', parent=self.root)
        if answer is None:
            return False
        return self.save_project() if answer else True

    def _reset_document(self, state, view=None, path=None):
        self.session.reset(state)
        self.project_path = Path(path).resolve() if path is not None else None
        self.selected = self.pending = self.drag_node = self.drag_element = None
        self.drag_bend = self.selected_bend = None
        self._clear_route()
        self.tool.set('select')
        self.mode = 'select'
        self._restore_view(view or ViewState())
        self._clean_project = self._snapshot()
        self._update_dirty()
        self._text('No current simulation result. Run Simulate DC for this document.')

    def new(self):
        if self._discard():
            self._reset_document(Schematic.from_document(CircuitDocument(Circuit(('n1',), ()))))

    def example(self):
        if self._discard():
            self._reset_document(divider_example())
            self.status.set('Example: select Simulate DC. Expected output at out: 8 V.')

    def open(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('Circuit JSON', '*.json')])
        if not path or not self._discard():
            return
        if path:
            try:
                state = Schematic.from_document(load_document(path))
                self._reset_document(state)
                self.status.set('Opened electrical circuit. Junction positions were arranged automatically.')
            except (ValueError, TypeError, OSError) as error:
                self._error(error)

    def open_project(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.root,
            filetypes=[('Schematic project', '*.ccproj.json'), ('JSON files', '*.json')])
        if not path or not self._discard():
            return
        try:
            project = load_project(path)
            self._reset_document(project.schematic, project.view, path)
            self.status.set('Project opened with its symbol layout, terminals, wires and view.')
        except (ValueError, TypeError, OSError) as error:
            self._error(error)

    def _save_project_to(self, path, *, replace_current=False):
        from tkinter import messagebox
        try:
            project = self._snapshot()
            try:
                write_project(project, path, overwrite=replace_current)
            except FileExistsError:
                if not messagebox.askyesno('Replace project file?',
                    'Replace the selected schematic project file?', parent=self.root):
                    return False
                write_project(project, path, overwrite=True)
            self.project_path = Path(path).resolve()
            self._clean_project = project
            self._update_dirty()
            self.status.set('Project saved, including symbols, terminals, wires, metadata and view.')
            return True
        except (ValueError, TypeError, OSError) as error:
            self._error(error)
            return False

    def save_project(self):
        if self.project_path is None:
            return self.save_project_as()
        return self._save_project_to(self.project_path, replace_current=True)

    def save_project_as(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.ccproj.json',
            filetypes=[('Schematic project', '*.ccproj.json')], confirmoverwrite=False)
        return self._save_project_to(path) if path else False

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
            lines += [f'{self.session.state.endpoint_label(node)}: {result.node_voltages[net]:.9g}' for node, net in mapping.items()]
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


def launch(state=None, *, project=None, path=None):
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise ValueError('Cannot initialize a Tk display; run the GUI in a desktop session with Tcl/Tk installed') from error
    CircuitEditor(root, state, project=project, project_path=path)
    root.mainloop()
