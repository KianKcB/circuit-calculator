"""Canvas symbols/labels/handles, separated from editor actions and persistence."""

import math

from .circuit import Resistor, VoltageSource
from .schematic import terminals, value_of, ComponentPlacement


def render_schematic(canvas, state, zoom, *, selected=None, selected_bend=None, pending=None, mode='select', preview=None):
    canvas.delete('all')
    positions = {p.node: (p.x * zoom, p.y * zoom) for p in state.positions}
    if preview:
        positions[preview.node] = (preview.x * zoom, preview.y * zoom)
    # Grid dots are decorative; only entity-tagged dots are electrical nodes.
    for x in range(0, 1600, 40):
        for y in range(0, 1200, 40):
            canvas.create_oval(x * zoom, y * zoom, x * zoom + 1, y * zoom + 1,
                               fill='#dce5ee', outline='')
    for wire in state.wires:
        color = '#b25b10' if selected == ('wire', wire.name) else '#448269'
        path = (positions[wire.first], *((p.x * zoom, p.y * zoom) for p in wire.bends), positions[wire.second])
        canvas.create_line(*(v for point in path for v in point), fill=color,
                            width=3, tags=(f'entity:wire:{wire.name}', 'circuit-content'))
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
        offset = index * 48 * zoom
        cx, cy = (x1 + x2) / 2 + px * offset, (y1 + y2) / 2 + py * offset
        if element.name in placed:
            placement = placed[element.name]
            cx, cy = placement.x * zoom, placement.y * zoom
            ux, uy = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[placement.rotation]
            px, py = -uy, ux
        radius = 21 * zoom
        start, end = (cx - ux * radius, cy - uy * radius), (cx + ux * radius, cy + uy * radius)
        tag = (f'entity:element:{element.name}', 'circuit-content')
        color = '#b25b10' if selected == ('element', element.name) else '#254e79'
        canvas.create_line(x1, y1, *start, fill=color, width=2, tags=tag)
        canvas.create_line(*end, x2, y2, fill=color, width=2, tags=tag)
        if type(element) is Resistor:
            points = []
            for i in range(9):
                along = -radius + 2 * radius * i / 8
                across = (6 * zoom * (-1 if i % 2 else 1)) if i not in (0, 8) else 0
                points.extend((cx + ux * along + px * across, cy + uy * along + py * across))
            canvas.create_line(*points, fill=color, width=2, tags=tag)
            unit = 'Ω'
        else:
            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                outline=color, width=2, fill='#f6f9fc', tags=tag)
            if type(element) is VoltageSource:
                for distance, label in ((-9, '+'), (9, '−')):
                    canvas.create_text(cx + ux * distance * zoom, cy + uy * distance * zoom,
                                        text=label, fill=color, tags=tag)
                unit = 'V'
            else:
                canvas.create_line(cx - ux * 11 * zoom, cy - uy * 11 * zoom,
                                    cx + ux * 11 * zoom, cy + uy * 11 * zoom,
                                    arrow='last', fill=color, width=2, tags=tag)
                unit = 'A'
        canvas.create_text(cx + px * 38 * zoom, cy + py * 38 * zoom,
                            text=f'{element.name}  {value_of(element):g} {unit}\n{state.endpoint_label(a)} → {state.endpoint_label(b)}',
                            anchor=('e' if px < 0 else 'w') if abs(px) > .6 else ('s' if py < 0 else 'n'),
                            fill=color, font=('Segoe UI', 9), tags=tag)
    owners = state.terminal_owners()
    for node, (x, y) in positions.items():
        kind = 'terminal' if node in owners else 'node'
        tag = (f'entity:{kind}:{node}', 'circuit-content')
        is_selected = selected == (kind, node) or pending == node
        color = '#b25b10' if is_selected else '#173b61'
        canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill=color, outline='white', width=2, tags=tag)
        canvas.create_text(x + 12, y - 13, text=state.endpoint_label(node), anchor='w', fill=color,
                            font=('Segoe UI', 10, 'bold'), tags=tag)
        if state.document.circuit.reference_node == node:
            canvas.create_line(x, y + 7, x, y + 18, fill=color, width=2, tags=tag)
            for width, dy in ((14, 18), (9, 23), (4, 28)):
                canvas.create_line(x - width, y + dy, x + width, y + dy, fill=color, width=2, tags=tag)
    content_region = canvas.bbox('circuit-content') or (0, 0, 1000, 700)
    if mode == 'select' and selected and selected[0] == 'wire':
        wire = next((w for w in state.wires if w.name == selected[1]), None)
        if wire is not None:
            for index, point in enumerate(wire.bends):
                x, y = point.x * zoom, point.y * zoom
                fill = '#b25b10' if selected_bend == (wire.name, index) else 'white'
                canvas.create_rectangle(x - 5, y - 5, x + 5, y + 5, fill=fill, outline='#b25b10', width=2,
                                        tags=(f'entity:bend:{wire.name}', f'bend-index:{index}'))
    return content_region


def render_component_preview(canvas, template, x, y, zoom):
    """Decorative placement outline; never has electrical hit/content tags."""
    placement = ComponentPlacement('preview', x, y, template.rotation)
    first, second = placement.terminal_coordinates()
    points = tuple(v * zoom for point in (first, second) for v in point)
    tag = 'paste-preview'
    color = '#b25b10'
    canvas.create_line(*points, fill=color, width=2, dash=(4, 3), tags=tag)
    cx, cy = x * zoom, y * zoom
    canvas.create_rectangle(cx - 22 * zoom, cy - 22 * zoom, cx + 22 * zoom, cy + 22 * zoom,
                            outline=color, width=2, dash=(4, 3), fill='#fff4e5', tags=tag)
    labels = ('a', 'b') if template.kind == 'resistor' else ('+', '−') if template.kind == 'voltage' else ('from', 'to')
    for point, label in zip((first, second), labels):
        px, py = (v * zoom for v in point)
        canvas.create_oval(px - 5, py - 5, px + 5, py + 5, fill='white', outline=color, tags=tag)
        canvas.create_text(px + 10, py - 12, text=label, fill=color, anchor='w', tags=tag)
    unit = {'resistor': 'ohm', 'voltage': 'V', 'current': 'A'}[template.kind]
    canvas.create_text(cx, cy + 32 * zoom, text=f'Paste {template.kind}: {template.value:g} {unit}',
                       fill=color, anchor='n', tags=tag)
