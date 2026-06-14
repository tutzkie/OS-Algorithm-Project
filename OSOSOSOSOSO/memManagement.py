"""
MVT Memory Simulator — Python/Tkinter port of mvt_memory_simulator_v2.html
Faithful recreation: same layout, same logic, same colors, same behavior.
+ Custom process addition/removal via UI form.
"""

import tkinter as tk
from tkinter import ttk

# ── Constants ────────────────────────────────────────────────────────────────
TOTAL   = 256
OS_SIZE = 40

JOBS = [
    {"id": 1, "mem": 60,  "burst": 10},
    {"id": 2, "mem": 100, "burst": 5},
    {"id": 3, "mem": 30,  "burst": 20},
    {"id": 4, "mem": 70,  "burst": 8},
    {"id": 5, "mem": 50,  "burst": 15},
]

PCOLS = ["#4A90D9", "#5BAD7A", "#E07A3A", "#9B6DB5", "#D4535A",
         "#3AAFB9", "#C97B3A", "#6B9B37", "#B55A8C", "#4A7DB5",
         "#8B5E3C", "#5A8F7B", "#C4704A", "#7B6DB5", "#B5A33A"]

STATUS_STYLE = {
    "waiting": ("#FAEEDA", "#854F0B"),
    "ready":   ("#E6F1FB", "#185FA5"),
    "running": ("#EAF3DE", "#3B6D11"),
    "done":    ("#D3D1C7", "#2C2C2A"),
}

EVENT_COLORS = {
    "green": "#3B6D11",
    "blue":  "#185FA5",
    "red":   "#A32D2D",
    "amber": "#854F0B",
    "gray":  "#888888",
}

BG      = "#FFFFFF"
BG2     = "#F5F5F3"
BORDER  = "#D8D6CE"
TXT     = "#1A1A18"
TXT2    = "#666660"
TXT3    = "#AAAAAA"
OS_BG   = "#5F5E5A"
OS_FG   = "#F1EFE8"
FREE_BG = "#F0EFE9"
FREE_FG = "#AAAAAA"

MEM_W   = 160
MEM_H   = 300
GANTT_H = 14


# ── Simulator logic ───────────────────────────────────────────────────────────

class Simulator:
    def __init__(self):
        self.compaction_on = False
        self.base_jobs = [dict(j) for j in JOBS]
        self.reset()

    def reset(self):
        self.time     = 0
        self.procs    = [
            {**j, "remaining": j["burst"], "status": "waiting",
             "ci": i % len(PCOLS), "addr": -1}
            for i, j in enumerate(self.base_jobs)
        ]
        self.input_q  = list(self.procs)
        self.holes    = [{"start": OS_SIZE, "size": TOTAL - OS_SIZE}]
        self.gantt    = {p["id"]: [] for p in self.procs}
        self.events   = []
        self.rr_q     = []
        self.rr_left  = 0
        self.cur_proc = None
        self.finished = False

    def add_job(self, mem, burst):
        """Add a new job. Returns (ok, msg). Only valid before simulation starts."""
        if self.time > 0:
            return False, "Reset the simulation before adding jobs."
        if mem < 1 or mem > TOTAL - OS_SIZE:
            return False, f"Memory must be 1–{TOTAL - OS_SIZE}K."
        if burst < 1:
            return False, "Burst time must be at least 1."
        new_id = max((j["id"] for j in self.base_jobs), default=0) + 1
        self.base_jobs.append({"id": new_id, "mem": mem, "burst": burst})
        self.reset()
        return True, f"Job {new_id} added (mem={mem}K, burst={burst})."

    def remove_job(self, job_id):
        """Remove a job by id. Returns (ok, msg). Only valid before simulation starts."""
        if self.time > 0:
            return False, "Reset the simulation before removing jobs."
        before = len(self.base_jobs)
        self.base_jobs = [j for j in self.base_jobs if j["id"] != job_id]
        if len(self.base_jobs) == before:
            return False, f"No job with id {job_id}."
        self.reset()
        return True, f"Job {job_id} removed."

    def log(self, msg, color="gray"):
        self.events.insert(0, (msg, color))
        if len(self.events) > 40:
            self.events.pop()

    def merge_holes(self):
        self.holes.sort(key=lambda h: h["start"])
        merged = []
        for h in self.holes:
            if merged and merged[-1]["start"] + merged[-1]["size"] == h["start"]:
                merged[-1]["size"] += h["size"]
            else:
                merged.append(dict(h))
        self.holes = merged

    def allocate(self, proc):
        for i, hole in enumerate(self.holes):
            if hole["size"] >= proc["mem"]:
                proc["addr"]   = hole["start"]
                proc["status"] = "ready"
                hole["start"] += proc["mem"]
                hole["size"]  -= proc["mem"]
                if hole["size"] == 0:
                    self.holes.pop(i)
                self.merge_holes()
                return True
        return False

    def free_mem(self, proc):
        self.holes.append({"start": proc["addr"], "size": proc["mem"]})
        proc["addr"] = -1
        self.merge_holes()

    def compact(self):
        in_mem = sorted([p for p in self.procs if p["addr"] >= 0],
                        key=lambda p: p["addr"])
        cur   = OS_SIZE
        moved = False
        for p in in_mem:
            if p["addr"] != cur:
                moved = True
                p["addr"] = cur
            cur += p["mem"]
        total_free = TOTAL - cur
        self.holes = [{"start": cur, "size": total_free}] if total_free > 0 else []
        return moved

    def try_load(self, algo):
        for proc in list(self.input_q):
            if proc["status"] == "waiting":
                if self.allocate(proc):
                    self.input_q = [p for p in self.input_q if p["id"] != proc["id"]]
                    self.log(
                        f"t={self.time}: Job {proc['id']} loaded → addr {proc['addr']}, size {proc['mem']}K",
                        "green"
                    )
                    if algo == "sjf":
                        self.rr_q.append(proc)
                        self.rr_q.sort(key=lambda p: p["remaining"])
                    else:
                        self.rr_q.append(proc)

    def do_tick(self, proc, algo):
        proc["remaining"] -= 1
        self.rr_left      -= 1
        self.gantt[proc["id"]].append("run")
        compact_msg = None

        if proc["remaining"] <= 0:
            proc["status"] = "done"
            self.log(f"t={self.time}: Job {proc['id']} done — freed {proc['mem']}K", "red")
            self.free_mem(proc)
            if self.compaction_on:
                moved = self.compact()
                if moved:
                    freed = sum(h["size"] for h in self.holes)
                    self.log(f"t={self.time}: Compaction → {freed}K contiguous free", "amber")
                    compact_msg = (
                        f"t={self.time}: Compaction — holes merged into {freed}K contiguous block."
                    )
            self.try_load(algo)
            if self.cur_proc is proc:
                self.cur_proc = None
                self.rr_left  = 0
        else:
            proc["status"] = "running"

        return compact_msg

    def step(self, algo, quantum=5):
        if self.finished:
            return None

        self.time += 1
        self.try_load(algo)
        compact_msg = None

        if algo == "rr":
            if self.cur_proc and self.rr_left > 0:
                compact_msg = self.do_tick(self.cur_proc, algo)
            else:
                if self.cur_proc and self.cur_proc["status"] != "done":
                    self.cur_proc["status"] = "ready"
                    self.rr_q.append(self.cur_proc)
                self.cur_proc = self.rr_q.pop(0) if self.rr_q else None
                self.rr_left  = quantum
                if self.cur_proc:
                    self.cur_proc["status"] = "running"
                    compact_msg = self.do_tick(self.cur_proc, algo)

        elif algo == "fcfs":
            if self.cur_proc and self.cur_proc["status"] == "running":
                compact_msg = self.do_tick(self.cur_proc, algo)
            else:
                self.cur_proc = self.rr_q.pop(0) if self.rr_q else None
                if self.cur_proc:
                    self.cur_proc["status"] = "running"
                    compact_msg = self.do_tick(self.cur_proc, algo)

        else:  # sjf
            if self.cur_proc and self.cur_proc["status"] == "running":
                compact_msg = self.do_tick(self.cur_proc, algo)
            else:
                self.rr_q.sort(key=lambda p: p["remaining"])
                self.cur_proc = self.rr_q.pop(0) if self.rr_q else None
                if self.cur_proc:
                    self.cur_proc["status"] = "running"
                    compact_msg = self.do_tick(self.cur_proc, algo)

        for p in self.procs:
            if p["status"] not in ("running", "done"):
                if p["addr"] >= 0:
                    p["status"] = "ready"
                self.gantt[p["id"]].append("idle")

        if all(p["status"] == "done" for p in self.procs):
            self.finished = True
            self.log(f"t={self.time}: All jobs complete!", "blue")

        return compact_msg

    def get_fragmentation(self):
        if len(self.holes) <= 1:
            return 0
        total   = sum(h["size"] for h in self.holes)
        largest = max((h["size"] for h in self.holes), default=0)
        if total == 0:
            return 0
        return round(((total - largest) / total) * 100)

    def free_k(self):
        return sum(h["size"] for h in self.holes)


# ── GUI ───────────────────────────────────────────────────────────────────────

class App(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG)

        self.sim           = Simulator()
        self._banner_after = None
        self.algo_var      = tk.StringVar(value="rr")

        self._build_ui()
        self.after(60, self._render)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        self._build_banner()
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        self._build_content()

    def _build_topbar(self):
        top = tk.Frame(self, bg=BG, pady=8, padx=10)
        top.pack(fill="x")

        tk.Label(top, text="MVT Memory Simulator", bg=BG, fg=TXT,
                 font=("Helvetica", 13, "bold")).pack(side="left")

        seg_outer = tk.Frame(top, bg=BORDER)
        seg_outer.pack(side="left", padx=(12, 0))
        seg_inner = tk.Frame(seg_outer, bg=BORDER)
        seg_inner.pack(padx=1, pady=1)

        algo_map = [("Round Robin", "rr"), ("FCFS", "fcfs"), ("SJF", "sjf")]
        self._algo_btns = {}
        for label, val in algo_map:
            b = tk.Button(
                seg_inner, text=label, font=("Helvetica", 9),
                bd=0, padx=9, pady=5, cursor="hand2",
                command=lambda v=val: self._set_algo(v)
            )
            b.pack(side="left")
            self._algo_btns[val] = b
        self._update_algo_btns()

        # ── quantum field (only visible for RR) ───────────────────────────────
        self._quantum_frame = tk.Frame(top, bg=BG)
        self._quantum_frame.pack(side="left", padx=(6, 0))
        tk.Label(self._quantum_frame, text="q =", bg=BG, fg=TXT2,
                 font=("Helvetica", 9)).pack(side="left")
        self.quantum_var = tk.StringVar(value="5")
        self._quantum_entry = tk.Entry(
            self._quantum_frame, textvariable=self.quantum_var,
            width=3, font=("Helvetica", 9, "bold"),
            bg=BG2, fg=TXT, relief="solid",
            highlightbackground=BORDER, highlightthickness=1,
            bd=0, insertbackground=TXT, justify="center"
        )
        self._quantum_entry.pack(side="left", padx=(3, 0))

        self.compact_btn = tk.Button(
            top, text="⊞ Compaction: OFF",
            bg=BG2, fg=TXT2, font=("Helvetica", 9),
            bd=1, relief="solid", highlightbackground=BORDER,
            cursor="hand2", padx=9, pady=4,
            command=self._toggle_compaction
        )
        self.compact_btn.pack(side="left", padx=(8, 0))

        self.time_lbl = tk.Label(
            top, text="t = 0", bg=BG2, fg=TXT,
            font=("Helvetica", 11, "bold"),
            padx=10, pady=4, bd=1, relief="solid",
            highlightbackground=BORDER
        )
        self.time_lbl.pack(side="left", padx=(8, 0))

        self.step_btn = tk.Button(
            top, text="▶  Step +1",
            bg=TXT, fg=BG, font=("Helvetica", 9, "bold"),
            bd=0, padx=10, pady=5, cursor="hand2",
            command=self._step
        )
        self.step_btn.pack(side="left", padx=(8, 0))

        tk.Button(
            top, text="↺  Reset",
            bg=BG2, fg=TXT2, font=("Helvetica", 9),
            bd=1, relief="solid", highlightbackground=BORDER,
            cursor="hand2", padx=9, pady=4,
            command=self._reset
        ).pack(side="left", padx=(6, 0))

    def _build_banner(self):
        self.banner_frame = tk.Frame(
            self, bg="#FAEEDA",
            highlightbackground="#EF9F27", highlightthickness=1
        )
        self.banner_lbl = tk.Label(
            self.banner_frame, text="",
            bg="#FAEEDA", fg="#854F0B",
            font=("Helvetica", 9, "bold"), padx=10, pady=5
        )
        self.banner_lbl.pack()

    def _build_content(self):
        content = tk.Frame(self, bg=BG, padx=10, pady=8)
        content.pack(fill="both", expand=True)

        # ── LEFT: memory map ──────────────────────────────────────────────────
        left_wrap = tk.Frame(content, bg=BG, width=MEM_W + 24)
        left_wrap.pack(side="left", fill="y", padx=(0, 8))
        left_wrap.pack_propagate(False)

        mem_panel = self._make_panel(left_wrap, "Memory (256K)")
        mem_panel.pack(fill="both", expand=True)

        self.mem_canvas = tk.Canvas(
            mem_panel, bg=FREE_BG, bd=0,
            highlightthickness=1, highlightbackground=BORDER,
            width=MEM_W, height=MEM_H
        )
        self.mem_canvas.pack(pady=(2, 4))

        frow = tk.Frame(mem_panel, bg=BG)
        frow.pack(fill="x")
        tk.Label(frow, text="External frag.", bg=BG, fg=TXT3,
                 font=("Helvetica", 8)).pack(side="left")
        self.frag_pct_lbl = tk.Label(frow, text="0%", bg=BG, fg=TXT3,
                                      font=("Helvetica", 8))
        self.frag_pct_lbl.pack(side="right")

        fbar_bg = tk.Frame(mem_panel, bg=BORDER, height=5, width=MEM_W)
        fbar_bg.pack(anchor="w", pady=(2, 4))
        fbar_bg.pack_propagate(False)
        self._frag_bar_bg = fbar_bg
        self.frag_bar = tk.Frame(fbar_bg, bg="#E24B4A", height=5)
        self.frag_bar.place(x=0, y=0, relheight=1.0, width=0)

        self.free_lbl = tk.Label(mem_panel, text="Free: 216K (1 hole)",
                                 bg=BG, fg=TXT3, font=("Helvetica", 8))
        self.free_lbl.pack(anchor="w")

        # ── RIGHT ─────────────────────────────────────────────────────────────
        right = tk.Frame(content, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        # Add process panel
        apanel = self._make_panel(right, "Add / remove process")
        apanel.pack(fill="x", pady=(0, 6))
        self._build_add_proc_form(apanel)

        # Process table
        tpanel = self._make_panel(right, "Process table")
        tpanel.pack(fill="x", pady=(0, 6))
        self._build_proc_table(tpanel)

        # Gantt
        gpanel = self._make_panel(right, "Gantt chart")
        gpanel.pack(fill="x", pady=(0, 6))
        gh = 20 + len(self.sim.base_jobs) * (GANTT_H + 6)
        self.gantt_canvas = tk.Canvas(
            gpanel, bg=BG, bd=0, highlightthickness=0, height=gh
        )
        self.gantt_canvas.pack(fill="x", expand=True)
        self.gantt_canvas.bind("<Configure>", lambda e: self._render_gantt())

        # Events
        epanel = self._make_panel(right, "Events")
        epanel.pack(fill="both", expand=True)
        self._build_event_log(epanel)

    def _build_add_proc_form(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x")

        # Mem entry
        tk.Label(row, text="Mem (K):", bg=BG, fg=TXT2,
                 font=("Helvetica", 9)).pack(side="left")
        self.add_mem_var = tk.StringVar(value="40")
        tk.Entry(row, textvariable=self.add_mem_var, width=6,
                 font=("Helvetica", 9), bg=BG2, fg=TXT,
                 relief="solid", highlightbackground=BORDER,
                 highlightthickness=1, bd=0,
                 insertbackground=TXT).pack(side="left", padx=(4, 10))

        # Burst entry
        tk.Label(row, text="Burst:", bg=BG, fg=TXT2,
                 font=("Helvetica", 9)).pack(side="left")
        self.add_burst_var = tk.StringVar(value="10")
        tk.Entry(row, textvariable=self.add_burst_var, width=6,
                 font=("Helvetica", 9), bg=BG2, fg=TXT,
                 relief="solid", highlightbackground=BORDER,
                 highlightthickness=1, bd=0,
                 insertbackground=TXT).pack(side="left", padx=(4, 10))

        # Add button
        tk.Button(
            row, text="+ Add",
            bg="#3B6D11", fg="#fff", font=("Helvetica", 9, "bold"),
            bd=0, padx=10, pady=3, cursor="hand2",
            activebackground="#27500A", activeforeground="#fff",
            command=self._add_process
        ).pack(side="left", padx=(0, 16))

        # Separator
        tk.Frame(row, bg=BORDER, width=1, height=20).pack(side="left", padx=(0, 14))

        # Remove by ID
        tk.Label(row, text="Remove job ID:", bg=BG, fg=TXT2,
                 font=("Helvetica", 9)).pack(side="left")
        self.remove_id_var = tk.StringVar(value="")
        tk.Entry(row, textvariable=self.remove_id_var, width=4,
                 font=("Helvetica", 9), bg=BG2, fg=TXT,
                 relief="solid", highlightbackground=BORDER,
                 highlightthickness=1, bd=0,
                 insertbackground=TXT).pack(side="left", padx=(4, 6))
        tk.Button(
            row, text="Remove",
            bg="#A32D2D", fg="#fff", font=("Helvetica", 9, "bold"),
            bd=0, padx=10, pady=3, cursor="hand2",
            activebackground="#791F1F", activeforeground="#fff",
            command=self._remove_process
        ).pack(side="left")

        # Feedback label
        self.add_status_lbl = tk.Label(
            parent, text="", bg=BG, fg=TXT3, font=("Helvetica", 8)
        )
        self.add_status_lbl.pack(anchor="w", pady=(3, 0))

    def _make_panel(self, parent, title):
        outer = tk.Frame(parent, bg=BORDER)
        inner = tk.Frame(outer, bg=BG, padx=8, pady=6)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(inner, text=title.upper(), bg=BG, fg=TXT2,
                 font=("Helvetica", 8, "bold")).pack(anchor="w", pady=(0, 4))
        def _pack(**kw):
            outer.pack(**kw)
        inner.pack = _pack
        return inner

    def _build_proc_table(self, parent):
        cols   = ("Job", "Mem", "Burst", "Rem", "Status", "Addr")
        widths = (60, 48, 52, 42, 100, 65)
        self.proc_tree = ttk.Treeview(
            parent, columns=cols, show="headings",
            height=len(JOBS), selectmode="none"
        )
        for col, w in zip(cols, widths):
            self.proc_tree.heading(col, text=col, anchor="w")
            self.proc_tree.column(col, width=w, minwidth=w, stretch=False, anchor="w")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("MVT.Treeview",
                        background=BG, fieldbackground=BG, foreground=TXT,
                        rowheight=24, font=("Helvetica", 10), borderwidth=0)
        style.configure("MVT.Treeview.Heading",
                        background=BG2, foreground=TXT2,
                        font=("Helvetica", 9), relief="flat")
        style.map("MVT.Treeview",
                  background=[("selected", BG)],
                  foreground=[("selected", TXT)])
        self.proc_tree.configure(style="MVT.Treeview")

        for st, (bg, fg) in STATUS_STYLE.items():
            self.proc_tree.tag_configure(st, background=bg, foreground=fg)

        self.proc_tree.pack(fill="x")

    def _build_event_log(self, parent):
        wrap = tk.Frame(parent, bg=BG2,
                        highlightbackground=BORDER, highlightthickness=1)
        wrap.pack(fill="both", expand=True)

        sb = tk.Scrollbar(wrap, width=12)
        sb.pack(side="right", fill="y")

        self.event_text = tk.Text(
            wrap, bg=BG2, fg=TXT2, bd=0,
            font=("Courier", 9), height=7,
            highlightthickness=0, state="disabled",
            wrap="word", yscrollcommand=sb.set
        )
        sb.config(command=self.event_text.yview)
        self.event_text.pack(fill="both", expand=True, padx=4, pady=4)

        for key, col in EVENT_COLORS.items():
            self.event_text.tag_configure(key, foreground=col)

    # ── Add / Remove actions ──────────────────────────────────────────────────

    def _add_process(self):
        try:
            mem   = int(self.add_mem_var.get().strip())
            burst = int(self.add_burst_var.get().strip())
        except ValueError:
            self._set_add_status("Mem and Burst must be integers.", error=True)
            return

        ok, msg = self.sim.add_job(mem, burst)
        self._set_add_status(msg, error=not ok)
        if ok:
            self._rebuild_gantt_height()
            self._render()

    def _remove_process(self):
        raw = self.remove_id_var.get().strip()
        if not raw:
            self._set_add_status("Enter a Job ID to remove.", error=True)
            return
        try:
            job_id = int(raw)
        except ValueError:
            self._set_add_status("Job ID must be an integer.", error=True)
            return

        ok, msg = self.sim.remove_job(job_id)
        self._set_add_status(msg, error=not ok)
        if ok:
            self.remove_id_var.set("")
            self._rebuild_gantt_height()
            self._render()

    def _set_add_status(self, msg, error=False):
        self.add_status_lbl.config(
            text=msg,
            fg="#A32D2D" if error else "#3B6D11"
        )
        self.after(3500, lambda: self.add_status_lbl.config(text=""))

    def _rebuild_gantt_height(self):
        n  = len(self.sim.base_jobs)
        gh = 20 + n * (GANTT_H + 6)
        self.gantt_canvas.config(height=gh)

    # ── Sim actions ───────────────────────────────────────────────────────────

    def _update_algo_btns(self):
        val = self.algo_var.get()
        for v, b in self._algo_btns.items():
            b.config(bg=TXT if v == val else BG2,
                     fg=BG  if v == val else TXT2)
        # show quantum entry only for RR
        if hasattr(self, "_quantum_frame"):
            if val == "rr":
                self._quantum_frame.pack(side="left", padx=(6, 0))
            else:
                self._quantum_frame.pack_forget()

    def _set_algo(self, val):
        self.algo_var.set(val)
        self._update_algo_btns()
        self._reset()

    def _toggle_compaction(self):
        self.sim.compaction_on = not self.sim.compaction_on
        state = "ON" if self.sim.compaction_on else "OFF"
        self.compact_btn.config(
            bg="#185FA5" if self.sim.compaction_on else BG2,
            fg="#ffffff"  if self.sim.compaction_on else TXT2,
            text=f"⊞ Compaction: {state}"
        )
        self._reset()

    def _reset(self):
        self.sim.reset()
        self._hide_banner()
        self.step_btn.config(state="normal")
        self._rebuild_gantt_height()
        self._render()

    def _get_quantum(self):
        try:
            q = int(self.quantum_var.get().strip())
            return max(1, q)
        except ValueError:
            self.quantum_var.set("5")
            return 5

    def _step(self):
        compact_msg = self.sim.step(self.algo_var.get(), quantum=self._get_quantum())
        if compact_msg:
            self._show_banner(compact_msg)
        if self.sim.finished:
            self.step_btn.config(state="disabled")
        self._render()

    # ── Banner ────────────────────────────────────────────────────────────────

    def _show_banner(self, msg):
        self.banner_lbl.config(text=f"⬇ {msg}")
        self.banner_frame.pack(fill="x", padx=10, pady=(0, 4))
        if self._banner_after:
            self.after_cancel(self._banner_after)
        self._banner_after = self.after(3000, self._hide_banner)

    def _hide_banner(self):
        self.banner_frame.pack_forget()
        self._banner_after = None

    # ── Render ────────────────────────────────────────────────────────────────

    def _render(self):
        self.time_lbl.config(text=f"t = {self.sim.time}")
        self._render_mem()
        self._render_proc_table()
        self._render_gantt()
        self._render_events()

    def _render_mem(self):
        c = self.mem_canvas
        c.delete("all")
        W, H = MEM_W, MEM_H

        segs = [{"size": OS_SIZE, "label": f"OS\n{OS_SIZE}K",
                  "bg": OS_BG, "fg": OS_FG}]
        in_mem = sorted([p for p in self.sim.procs if p["addr"] >= 0],
                        key=lambda p: p["addr"])
        cur = OS_SIZE
        for p in in_mem:
            if p["addr"] > cur:
                gap = p["addr"] - cur
                segs.append({"size": gap, "label": f"free\n{gap}K",
                              "bg": FREE_BG, "fg": FREE_FG})
            segs.append({"size": p["mem"],
                         "label": f"J{p['id']}\n{p['mem']}K",
                         "bg": PCOLS[p["ci"]], "fg": "#fff"})
            cur = p["addr"] + p["mem"]
        if cur < TOTAL:
            gap = TOTAL - cur
            segs.append({"size": gap, "label": f"free\n{gap}K",
                          "bg": FREE_BG, "fg": FREE_FG})

        y = H
        for seg in segs:
            h = max(int(seg["size"] / TOTAL * H), 2)
            y -= h
            c.create_rectangle(0, y, W, y + h,
                                fill=seg["bg"], outline=BORDER, width=0.5)
            lines  = seg["label"].split("\n")
            mid_y  = y + h // 2
            offset = 6 if len(lines) > 1 and h >= 28 else 0
            if h >= 16:
                c.create_text(W // 2, mid_y - offset,
                              text=lines[0], fill=seg["fg"],
                              font=("Helvetica", 8, "bold"))
                if offset:
                    c.create_text(W // 2, mid_y + offset + 2,
                                  text=lines[1], fill=seg["fg"],
                                  font=("Helvetica", 7))

        frag  = self.sim.get_fragmentation()
        bar_w = int(MEM_W * frag / 100)
        self.frag_pct_lbl.config(text=f"{frag}%")
        self.frag_bar.place(x=0, y=0, relheight=1.0, width=bar_w)

        fk = self.sim.free_k()
        hn = len(self.sim.holes)
        self.free_lbl.config(
            text=f"Free: {fk}K ({hn} hole{'s' if hn != 1 else ''})"
        )

    def _render_proc_table(self):
        n = len(self.sim.procs)
        self.proc_tree.config(height=max(3, min(n, 12)))

        for row in self.proc_tree.get_children():
            self.proc_tree.delete(row)
        for p in self.sim.procs:
            addr = f"{p['addr']}K" if p["addr"] >= 0 else "—"
            self.proc_tree.insert(
                "", "end",
                values=(f"● J{p['id']}", f"{p['mem']}K",
                        p["burst"], p["remaining"], p["status"], addr),
                tags=(p["status"],)
            )

    def _render_gantt(self):
        c = self.gantt_canvas
        c.delete("all")
        W = c.winfo_width()
        if W <= 1:
            return
        maxT    = max(self.sim.time, 1)
        lbl_w   = 44
        track_w = W - lbl_w - 8
        y0      = 14

        for t in range(0, maxT + 1, 5):
            x = lbl_w + int(t / maxT * track_w)
            c.create_text(x, y0 - 4, text=str(t), fill=TXT3,
                          font=("Helvetica", 7), anchor="s")

        for idx, p in enumerate(self.sim.procs):
            y = y0 + idx * (GANTT_H + 6)
            c.create_text(lbl_w - 4, y + GANTT_H // 2,
                          text=f"J{p['id']}", fill=TXT2,
                          font=("Helvetica", 8), anchor="e")
            c.create_rectangle(lbl_w, y, lbl_w + track_w, y + GANTT_H,
                                fill=BG2, outline="")
            ticks = self.sim.gantt[p["id"]]
            if ticks:
                cell_w = track_w / maxT
                for ti, tick in enumerate(ticks):
                    x0 = lbl_w + int(ti * cell_w)
                    x1 = lbl_w + int((ti + 1) * cell_w)
                    if tick == "run":
                        c.create_rectangle(x0, y, x1, y + GANTT_H,
                                           fill=PCOLS[p["ci"]], outline="")

    def _render_events(self):
        self.event_text.config(state="normal")
        self.event_text.delete("1.0", "end")
        for msg, color in self.sim.events:
            self.event_text.insert("end", msg + "\n", color)
        self.event_text.config(state="disabled")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    root.title("MVT Memory Simulator")
    root.minsize(720, 620)
    root.configure(bg=BG)
    app = App(root)
    app.pack(fill="both", expand=True)
    root.mainloop()