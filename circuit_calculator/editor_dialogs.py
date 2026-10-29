"""Optional Tk forms. Importing this module never imports or initializes Tk."""

from dataclasses import replace

from .circuit_io import CircuitDocument


def ask_project_details(parent, document):
    """Return validated (title, description), or None; never change the graph."""
    if type(document) is not CircuitDocument:
        raise TypeError('Expected a CircuitDocument')
    import tkinter as tk
    from tkinter import simpledialog, ttk

    class DetailsDialog(simpledialog.Dialog):
        def body(self, master):
            self.resizable(False, False)
            ttk.Label(master, text='Title (up to 256 characters)').grid(row=0, column=0, sticky='w', pady=(4, 2))
            self.title_entry = ttk.Entry(master, width=66)
            self.title_entry.grid(row=1, column=0, sticky='ew', pady=(0, 10))
            self.title_entry.insert(0, document.title)
            self.title_entry.selection_range(0, 'end')
            ttk.Label(master, text='Description (up to 4096 characters)').grid(row=2, column=0, sticky='w')
            frame = ttk.Frame(master)
            frame.grid(row=3, column=0, sticky='nsew', pady=4)
            self.description = tk.Text(frame, width=64, height=9, wrap='word', undo=True)
            self.description.pack(side='left', fill='both', expand=True)
            scroll = ttk.Scrollbar(frame, orient='vertical', command=self.description.yview)
            scroll.pack(side='right', fill='y')
            self.description.configure(yscrollcommand=scroll.set)
            self.description.insert('1.0', document.description)
            self.description.bind('<Control-Return>', self._apply_key)
            self.error = tk.StringVar()
            ttk.Label(master, textvariable=self.error, foreground='#a22d22', wraplength=540).grid(row=4, column=0, sticky='w')
            ttk.Label(master, text='Enter adds a description line. Ctrl+Enter applies. Save Project writes changes to disk.',
                      wraplength=540).grid(row=5, column=0, sticky='w', pady=5)
            return self.title_entry

        def buttonbox(self):
            box = ttk.Frame(self)
            self.apply_button = ttk.Button(box, text='Apply', command=self.ok)
            self.apply_button.pack(side='left', padx=5, pady=5)
            self.cancel_button = ttk.Button(box, text='Cancel', command=self.cancel)
            self.cancel_button.pack(side='left', padx=5, pady=5)
            box.pack()
            self.bind('<Return>', self._return_key)
            self.bind('<Control-Return>', self._apply_key)
            self.bind('<Escape>', self.cancel)

        def _return_key(self, event):
            if event.widget is not self.description:
                if event.widget is self.cancel_button:
                    self.cancel()
                else:
                    self.ok()
            return 'break'

        def _apply_key(self, event):
            self.ok()
            return 'break'

        def validate(self):
            title = self.title_entry.get()
            description = self.description.get('1.0', 'end-1c')
            try:
                replace(document, title=title, description=description)
            except (TypeError, ValueError) as error:
                self.error.set(str(error))
                self.initial_focus = self.description if 'description' in str(error) else self.title_entry
                return False
            self._validated = (title, description)
            return True

        def apply(self):
            self.result = self._validated

        def destroy(self):
            # Release the Tcl variable here, before a solver worker can collect
            # cycles left by closed widget wrappers on another thread.
            if hasattr(self, 'error'):
                self.error = None
            super().destroy()

    return DetailsDialog(parent, 'Project details').result


def ask_find_item(parent, state):
    """Return an exact selection identity, never infer it from a display string."""
    from .navigation import catalog_items, filter_items
    items = catalog_items(state)
    import tkinter as tk
    from tkinter import simpledialog, ttk

    class FindDialog(simpledialog.Dialog):
        def body(self, master):
            self.resizable(False, False)
            self.query, self.status = tk.StringVar(), tk.StringVar()
            self._rows = {f'item{i}': item for i, item in enumerate(items)}
            ttk.Label(master, text='Name or terminal label (up to 256 characters)').pack(anchor='w')
            self.entry = ttk.Entry(master, width=64, textvariable=self.query)
            self.entry.pack(fill='x', pady=(3, 8))
            frame = ttk.Frame(master, width=480, height=260)
            frame.pack(fill='both', expand=True)
            frame.pack_propagate(False)
            self.tree = ttk.Treeview(frame, columns=('kind', 'name'), show='headings', height=11, selectmode='browse')
            self.tree.heading('kind', text='Kind')
            self.tree.heading('name', text='Name / terminal label')
            self.tree.column('kind', width=100, stretch=False)
            self.tree.column('name', width=360, stretch=False)
            scroll = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
            horizontal = ttk.Scrollbar(frame, orient='horizontal', command=self.tree.xview)
            self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
            scroll.pack(side='right', fill='y')
            horizontal.pack(side='bottom', fill='x')
            self.tree.pack(side='left', fill='both', expand=True)
            ttk.Label(master, textvariable=self.status, wraplength=470).pack(anchor='w', pady=6)
            self.tree.bind('<Double-Button-1>', self._double_click)
            self.tree.bind('<<TreeviewSelect>>', self._selection_changed)
            self.entry.bind('<Down>', self._focus_list)
            self._trace = self.query.trace_add('write', self._filter)
            self._filter()
            return self.entry

        def buttonbox(self):
            box = ttk.Frame(self)
            self.show_button = ttk.Button(box, text='Show item', command=self.ok)
            self.show_button.pack(side='left', padx=5, pady=5)
            self.cancel_button = ttk.Button(box, text='Cancel', command=self.cancel)
            self.cancel_button.pack(side='left', padx=5, pady=5)
            box.pack()
            self.bind('<Return>', self._return_key)
            self.bind('<Escape>', self.cancel)
            self._selection_changed()

        def _filter(self, *args):
            old = self.tree.selection()
            self.tree.delete(*self.tree.get_children())
            try:
                matches = set(filter_items(items, self.query.get()))
            except (ValueError, TypeError) as error:
                self.status.set(str(error))
                self._selection_changed()
                return
            kinds = {'element': 'Component', 'node': 'Junction', 'terminal': 'Terminal', 'wire': 'Wire'}
            for row, item in self._rows.items():
                if item in matches:
                    self.tree.insert('', 'end', iid=row, values=(kinds[item.kind], item.label))
            rows = self.tree.get_children()
            if rows:
                selected = old[0] if old and old[0] in rows else rows[0]
                self.tree.selection_set(selected)
                self.tree.focus(selected)
                self.tree.see(selected)
            self.status.set(f'{len(rows)} matching items. Show item selects and centers without changing zoom.' if rows else 'No matching items.')
            self._selection_changed()

        def _selection_changed(self, event=None):
            if hasattr(self, 'show_button'):
                self.show_button.configure(state='normal' if self.tree.selection() else 'disabled')

        def _focus_list(self, event):
            self.tree.focus_set()
            return 'break'

        def _double_click(self, event):
            row = self.tree.identify_row(event.y)
            if row:
                self.tree.selection_set(row)
                self.ok()
            return 'break'

        def _return_key(self, event):
            self.cancel() if event.widget is self.cancel_button else self.ok()
            return 'break'

        def validate(self):
            selected = self.tree.selection()
            if not selected:
                self.status.set('Choose a matching item, or change the search text.')
                return False
            self._selected = self._rows[selected[0]].selection
            return True

        def apply(self):
            self.result = self._selected

        def destroy(self):
            if hasattr(self, '_trace'):
                self.query.trace_remove('write', self._trace)
            self.query = self.status = None
            super().destroy()

    return FindDialog(parent, 'Find item').result
