"""Opt-in Tk panel for a transient DC voltage probe; no document mutations."""

from .probe import probe_text


class VoltageProbePanel:
    def __init__(self, parent, session, *, key_command):
        from tkinter import ttk
        import tkinter as tk
        self.session = session
        self.revision = None
        self.nodes = ()
        self.solving = False
        self._text = None
        self.pickers = []
        for label in ('A (+)', 'B (−)'):
            ttk.Label(parent, text=label).pack(anchor='w', padx=8, pady=(6, 2))
            picker = ttk.Combobox(parent, state='readonly', width=28)
            picker.pack(fill='x', padx=8)
            picker.bind('<<ComboboxSelected>>', lambda event: self.refresh())
            self.pickers.append(picker)
        buttons = ttk.Frame(parent)
        buttons.pack(fill='x', padx=8, pady=8)
        self.swap_button = ttk.Button(buttons, text='Swap A / B', command=self.swap)
        self.swap_button.pack(side='left')
        self.clear_button = ttk.Button(buttons, text='Clear', command=self.clear)
        self.clear_button.pack(side='left', padx=4)
        ttk.Label(parent, text='Probe choices clear after circuit edits, Undo/Redo or opening a project.',
                  wraplength=240).pack(anchor='w', padx=8, pady=4)
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True)
        self.output = tk.Text(frame, width=34, wrap='word', relief='flat', bg='white',
                              padx=10, pady=10, state='disabled', font=('Consolas', 10))
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.output.pack(side='left', fill='both', expand=True)
        self.output.bind('<Control-KeyPress>', key_command)

    def endpoints(self):
        return tuple(self.nodes[p.current()] if 0 <= p.current() < len(self.nodes) else None
                     for p in self.pickers)

    def refresh(self, *, solving=None):
        if solving is not None:
            self.solving = solving
        if self.revision != self.session.revision:
            self.revision = self.session.revision
            self.nodes = self.session.state.document.circuit.nodes
            # Numbered rows disambiguate arbitrary free-node and terminal labels.
            labels = tuple(f'{i + 1}. {self.session.state.endpoint_label(n)}' for i, n in enumerate(self.nodes))
            for picker in self.pickers:
                picker.configure(values=labels)
                picker.set('')
        text = probe_text(self.session.state, *self.endpoints(), self.session.result, solving=self.solving)
        if text != self._text:
            self.output.configure(state='normal')
            self.output.delete('1.0', 'end')
            self.output.insert('1.0', text)
            self.output.configure(state='disabled')
            self._text = text

    def swap(self):
        first, second = (p.current() for p in self.pickers)
        for picker, index in zip(self.pickers, (second, first)):
            picker.current(index) if index >= 0 else picker.set('')
        self.refresh()

    def clear(self):
        for picker in self.pickers:
            picker.set('')
        self.refresh()
