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
