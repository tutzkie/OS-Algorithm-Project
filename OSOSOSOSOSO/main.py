"""
OS Simulations Hub — unified launcher for all operating-system simulators.
Run this file to open the homepage and navigate to each simulation.
"""

import tkinter as tk
from tkinter import font as tkfont

from cpuSched import App as CpuSchedApp
from memManagement import App as MemMgmtApp
from pageReplacement import PageReplacementApp
from diskSched import DiskSchedulingApp
from DeadLock import DeadlockApp

# ── Hub palette ───────────────────────────────────────────────────────────────
HUB_BG     = "#0a0a0a"
HUB_BG2    = "#141414"
HUB_BORDER = "#2a2a2a"
HUB_TEXT   = "#e8e8e8"
HUB_MUTED  = "#7a7a7a"
HUB_ACCENT = "#5B8DF5"

SIMULATORS = [
    {
        "key": "cpu",
        "title": "CPU Scheduling",
        "subtitle": "Process scheduling algorithms",
        "desc": "Step through FCFS, SJF, SRTF, Round Robin, and Priority scheduling with live Gantt charts and turnaround statistics.",
        "accent": "#5B8DF5",
        "tag": "Scheduling",
        "factory": CpuSchedApp,
    },
    {
        "key": "memory",
        "title": "Memory Management",
        "subtitle": "MVT dynamic partitioning",
        "desc": "Simulate variable-size memory allocation, external fragmentation, compaction, and CPU scheduling over loaded jobs.",
        "accent": "#22C55E",
        "tag": "Memory",
        "factory": MemMgmtApp,
    },
    {
        "key": "page",
        "title": "Page Replacement",
        "subtitle": "Virtual memory paging",
        "desc": "Visualize FIFO, LRU, OPT, Second Chance, LFU, and MFU page replacement with frame-by-frame fault tracking.",
        "accent": "#A855F7",
        "tag": "Paging",
        "factory": PageReplacementApp,
    },
    {
        "key": "disk",
        "title": "Disk Scheduling",
        "subtitle": "I/O seek optimization",
        "desc": "Compare FCFS, SSTF, SCAN, C-SCAN, LOOK, and C-LOOK disk head movement with an interactive seek chart.",
        "accent": "#F5A023",
        "tag": "I/O",
        "factory": DiskSchedulingApp,
    },
    {
        "key": "deadlock",
        "title": "Deadlock",
        "subtitle": "Avoidance, detection & prevention",
        "desc": "Explore Banker's algorithm, deadlock detection, resource allocation graphs, and circular-wait prevention step by step.",
        "accent": "#F05070",
        "tag": "Concurrency",
        "factory": DeadlockApp,
    },
]

SIM_META = {s["key"]: s for s in SIMULATORS}


class HomePage(tk.Frame):
    def __init__(self, master, on_open):
        super().__init__(master, bg=HUB_BG)
        self.on_open = on_open
        self._build()

    def _build(self):
        outer = tk.Frame(self, bg=HUB_BG)
        outer.pack(fill="both", expand=True, padx=32, pady=28)

        # Header
        hdr = tk.Frame(outer, bg=HUB_BG)
        hdr.pack(fill="x", pady=(0, 28))

        tk.Label(
            hdr, text="OPERATING SYSTEMS", bg=HUB_BG, fg=HUB_MUTED,
            font=("Courier New", 10),
        ).pack(anchor="w")

        title_font = tkfont.Font(family="Segoe UI", size=26, weight="bold")
        tk.Label(
            hdr, text="Simulation Suite", bg=HUB_BG, fg=HUB_TEXT,
            font=title_font,
        ).pack(anchor="w", pady=(4, 0))

        tk.Label(
            hdr,
            text="Select a module below to launch an interactive step-by-step simulator.",
            bg=HUB_BG, fg=HUB_MUTED, font=("Segoe UI", 11),
        ).pack(anchor="w", pady=(8, 0))

        # Card grid (auto-sized: 3 columns when more than 4 simulators)
        grid = tk.Frame(outer, bg=HUB_BG)
        grid.pack(fill="both", expand=True)
        cols = 3 if len(SIMULATORS) > 4 else 2
        rows = (len(SIMULATORS) + cols - 1) // cols
        for c in range(cols):
            grid.columnconfigure(c, weight=1)
        for r in range(rows):
            grid.rowconfigure(r, weight=1)

        for i, sim in enumerate(SIMULATORS):
            row, col = divmod(i, cols)
            self._make_card(grid, sim).grid(
                row=row, column=col, sticky="nsew",
                padx=(0, 8) if col < cols - 1 else 0,
                pady=(0, 8) if row < rows - 1 else 0,
            )

        tk.Label(
            outer,
            text="OS Simulations  ·  2nd Year Sem 2",
            bg=HUB_BG, fg="#3a3a3a", font=("Courier New", 9),
        ).pack(side="bottom", anchor="w", pady=(16, 0))

    def _make_card(self, parent, sim):
        card = tk.Frame(
            parent, bg=HUB_BG2,
            highlightbackground=HUB_BORDER, highlightthickness=1,
            cursor="hand2",
        )

        accent = tk.Frame(card, bg=sim["accent"], height=3)
        accent.pack(fill="x")

        inner = tk.Frame(card, bg=HUB_BG2)
        inner.pack(fill="both", expand=True, padx=20, pady=18)

        top = tk.Frame(inner, bg=HUB_BG2)
        top.pack(fill="x")

        tk.Label(
            top, text=sim["tag"].upper(), bg=HUB_BG2, fg=sim["accent"],
            font=("Courier New", 8, "bold"),
        ).pack(side="left")

        tk.Label(
            top, text="→", bg=HUB_BG2, fg=HUB_MUTED,
            font=("Segoe UI", 14),
        ).pack(side="right")

        tk.Label(
            inner, text=sim["title"], bg=HUB_BG2, fg=HUB_TEXT,
            font=("Segoe UI", 15, "bold"), anchor="w",
        ).pack(fill="x", pady=(10, 2))

        tk.Label(
            inner, text=sim["subtitle"], bg=HUB_BG2, fg=HUB_MUTED,
            font=("Segoe UI", 10), anchor="w",
        ).pack(fill="x", pady=(0, 10))

        tk.Label(
            inner, text=sim["desc"], bg=HUB_BG2, fg="#9a9a9a",
            font=("Segoe UI", 9), anchor="nw", justify="left",
            wraplength=340,
        ).pack(fill="both", expand=True)

        open_btn = tk.Button(
            inner, text="Open simulator",
            bg=sim["accent"], fg="#0a0a0a",
            activebackground=sim["accent"], activeforeground="#0a0a0a",
            font=("Segoe UI", 9, "bold"), relief="flat",
            padx=14, pady=6, cursor="hand2",
            command=lambda k=sim["key"]: self.on_open(k),
        )
        open_btn.pack(anchor="w", pady=(12, 0))

        for widget in (card, inner, top, accent):
            widget.bind(
                "<Button-1>",
                lambda e, k=sim["key"]: self.on_open(k),
            )
        open_btn.bind("<Button-1>", lambda e, k=sim["key"]: self.on_open(k))

        def _enter(_):
            card.configure(highlightbackground=sim["accent"])

        def _leave(_):
            card.configure(highlightbackground=HUB_BORDER)

        card.bind("<Enter>", _enter)
        card.bind("<Leave>", _leave)

        return card


class SimulatorShell(tk.Frame):
    """Wraps a simulator with a top navigation bar."""

    def __init__(self, master, sim_key, on_home):
        super().__init__(master, bg=HUB_BG)
        self.sim_key = sim_key
        self.on_home = on_home
        self._sim_widget = None

        nav = tk.Frame(self, bg=HUB_BG2, height=48)
        nav.pack(fill="x")
        nav.pack_propagate(False)

        tk.Button(
            nav, text="←  Home",
            bg=HUB_BG2, fg=HUB_TEXT,
            activebackground=HUB_BORDER, activeforeground=HUB_TEXT,
            font=("Segoe UI", 10), relief="flat",
            padx=16, pady=8, cursor="hand2",
            command=self.on_home,
        ).pack(side="left", padx=12, pady=8)

        meta = SIM_META[sim_key]
        tk.Label(
            nav, text=meta["title"], bg=HUB_BG2, fg=HUB_TEXT,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left", padx=(4, 0))

        tk.Label(
            nav, text=meta["subtitle"], bg=HUB_BG2, fg=HUB_MUTED,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(10, 0))

        self.body = tk.Frame(self, bg=HUB_BG)
        self.body.pack(fill="both", expand=True)

    def load(self):
        if self._sim_widget is not None:
            return
        meta = SIM_META[self.sim_key]
        self._sim_widget = meta["factory"](self.body)
        self._sim_widget.pack(fill="both", expand=True)


class OSSimulatorHub(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OS Simulations")
        self.geometry("1080x740")
        self.minsize(860, 600)
        self.configure(bg=HUB_BG)

        self._current = "home"
        self._shells = {}

        self.container = tk.Frame(self, bg=HUB_BG)
        self.container.pack(fill="both", expand=True)

        self.home = HomePage(self.container, self.open_simulator)
        self.home.place(relwidth=1, relheight=1)

        for sim in SIMULATORS:
            shell = SimulatorShell(self.container, sim["key"], self.go_home)
            shell.place(relwidth=1, relheight=1)
            self._shells[sim["key"]] = shell

        self.show("home")

    def show(self, key):
        self._current = key
        if key == "home":
            self.home.tkraise()
            self.title("OS Simulations")
        else:
            shell = self._shells[key]
            shell.load()
            shell.tkraise()
            self.title(f"{SIM_META[key]['title']} — OS Simulations")

    def open_simulator(self, key):
        self.show(key)

    def go_home(self):
        self.show("home")


def main():
    app = OSSimulatorHub()
    app.mainloop()


if __name__ == "__main__":
    main()
