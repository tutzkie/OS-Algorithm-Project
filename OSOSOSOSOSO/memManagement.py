"""
Memory Management Simulator (MVT & MFT)
Python/Tkinter application simulating OS memory allocation and scheduling.
Includes dark mode theme with light green accents.
"""

import tkinter as tk
from tkinter import ttk

# ── Constants & Theme ────────────────────────────────────────────────────────
TOTAL   = 256
OS_SIZE = 40

# Fixed Partitions for MFT (Total = 216K)
MFT_PARTITIONS = [
    {"id": 1, "size": 80},
    {"id": 2, "size": 60},
    {"id": 3, "size": 46},
    {"id": 4, "size": 30},
]

JOBS = [
    {"id": 1, "mem": 60,  "burst": 10},
    {"id": 2, "mem": 100, "burst": 5},
    {"id": 3, "mem": 30,  "burst": 20},
    {"id": 4, "mem": 70,  "burst": 8},
    {"id": 5, "mem": 50,  "burst": 15},
]

# Dark Theme Palette with Light Green hints
BG       = "#0D0D0D"
BG2      = "#1A1A1A"
BORDER   = "#333333"
TXT      = "#F5F5F5"
TXT2     = "#CCCCCC"
TXT3     = "#888888"
ACCENT   = "#22C55E" # Light Green
ACCENT2  = "#1B5E20" # Darker Green for backgrounds

OS_BG    = "#263238"
OS_FG    = "#B0BEC5"
FREE_BG  = "#1F1F1F"
FREE_FG  = "#7A7A7A"
FRAG_BG  = "#4A148C" # Color for internal fragmentation

PCOLS = ["#4A90D9", "#5BAD7A", "#E07A3A", "#9B6DB5", "#D4535A",
         "#3AAFB9", "#C97B3A", "#6B9B37", "#B55A8C", "#4A7DB5"]

STATUS_STYLE = {
    "waiting": ("#332B00", "#FFD54F"),
    "ready":   ("#001A33", "#64B5F6"),
    "running": ("#003300", "#64DD17"),
    "done":    ("#222222", "#888888"),
}

EVENT_COLORS = {
    "green": ACCENT,
    "blue":  "#4FC3F7",
    "red":   "#E57373",
    "amber": "#FFB74D",
    "gray":  TXT3,
}

MEM_W   = 180
MEM_H   = 350
GANTT_H = 16


# ── Simulator Logic ──────────────────────────────────────────────────────────

class Simulator:
    def __init__(self):
        self.mem_tech      = "mvt" # "mvt" or "mft"
        self.compaction_on = False
        self.base_jobs     = [dict(j) for j in JOBS]
        self.reset()

    def reset(self):
        self.time     = 0
        self.procs    = [
            {**j, "remaining": j["burst"], "status": "waiting",
             "ci": i % len(PCOLS), "addr": -1, "part_id": None}
            for i, j in enumerate(self.base_jobs)
        ]
        self.input_q  = list(self.procs)
        
        # MVT setup
        self.holes    = [{"start": OS_SIZE, "size": TOTAL - OS_SIZE}]
        
        # MFT setup
        self.partitions = []
        cur_addr = OS_SIZE
        for p in MFT_PARTITIONS:
            self.partitions.append({
                "id": p["id"], "start": cur_addr, "size": p["size"], "job": None
            })
            cur_addr += p["size"]

        self.gantt    = {p["id"]: [] for p in self.procs}
        self.events   = []
        self.rr_q     = []
        self.rr_left  = 0
        self.cur_proc = None
        self.finished = False

    def add_job(self, mem, burst):
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
        if self.time > 0:
            return False, "Reset before removing jobs."
        before = len(self.base_jobs)
        self.base_jobs = [j for j in self.base_jobs if j["id"] != job_id]
        if len(self.base_jobs) == before:
            return False, f"No job with id {job_id}."
        self.reset()
        return True, f"Job {job_id} removed."

    def log(self, msg, color="gray"):
        self.events.insert(0, (msg, color))
        if len(self.events) > 50:
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
        if self.mem_tech == "mvt":
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
        else:
            # MFT Allocation (First Fit among partitions)
            for p in self.partitions:
                if p["job"] is None and p["size"] >= proc["mem"]:
                    p["job"] = proc["id"]
                    proc["addr"]    = p["start"]
                    proc["part_id"] = p["id"]
                    proc["status"]  = "ready"
                    return True
        return False

    def free_mem(self, proc):
        if self.mem_tech == "mvt":
            self.holes.append({"start": proc["addr"], "size": proc["mem"]})
            proc["addr"] = -1
            self.merge_holes()
        else:
            # MFT Free
            for p in self.partitions:
                if p["id"] == proc["part_id"]:
                    p["job"] = None
                    proc["addr"] = -1
                    proc["part_id"] = None
                    break

    def compact(self):
        if self.mem_tech == "mft": 
            return False # No compaction in MFT
        
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
                else:
                    # Optional: Check if MFT job is larger than the largest partition
                    if self.mem_tech == "mft" and proc["mem"] > max(p["size"] for p in self.partitions):
                        proc["status"] = "done"
                        proc["remaining"] = 0
                        self.input_q = [p for p in self.input_q if p["id"] != proc["id"]]
                        self.log(f"t={self.time}: Job {proc['id']} too large for MFT partitions! Dropped.", "red")

    def do_tick(self, proc, algo):
        proc["remaining"] -= 1
        self.rr_left      -= 1
        self.gantt[proc["id"]].append("run")
        compact_msg = None

        if proc["remaining"] <= 0:
            proc["status"] = "done"
            self.log(f"t={self.time}: Job {proc['id']} done — freed {proc['mem']}K", "blue")
            self.free_mem(proc)
            
            if self.mem_tech == "mvt" and self.compaction_on:
                moved = self.compact()
                if moved:
                    freed = sum(h["size"] for h in self.holes)
                    self.log(f"t={self.time}: Compaction → {freed}K contiguous free", "amber")
                    compact_msg = f"t={self.time}: Compaction — merged into {freed}K block."
            self.try_load(algo)
            
            if self.cur_proc is proc:
                self.cur_proc = None
                self.rr_left  = 0
        else:
            proc["status"] = "running"

        return compact_msg

    def step(self, algo, quantum=5):
        if self.finished: return None

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
            self.log(f"t={self.time}: All jobs complete!", "green")

        return compact_msg

    def get_fragmentation(self):
        if self.mem_tech == "mvt":
            if len(self.holes) <= 1: return 0
            total   = sum(h["size"] for h in self.holes)
            largest = max((h["size"] for h in self.holes), default=0)
            if total == 0: return 0
            return round(((total - largest) / total) * 100)
        else:
            # Internal Fragmentation for MFT
            int_frag = 0
            for p in self.partitions:
                if p["job"] is not None:
                    job = next((j for j in self.procs if j["id"] == p["job"]), None)
                    if job: int_frag += (p["size"] - job["mem"])
            return int_frag

    def free_k(self):
        if self.mem_tech == "mvt":
            return sum(h["size"] for h in self.holes)
        else:
            return sum(p["size"] for p in self.partitions if p["job"] is None)


# ── GUI ──────────────────────────────────────────────────────────────────────

class App(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG)
        self.sim           = Simulator()
        self._banner_after = None
        self.algo_var      = tk.StringVar(value="rr")
        self.mem_var       = tk.StringVar(value="mvt")

        self._build_ui()
        self.after(60, self._render)

    # ── UI Construction ──────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_topbar()
        self._build_banner()
        tk.Frame(self, bg=BORDER, height=2).pack(fill="x")
        self._build_content()
        self._update_toggles() # Run this last so all UI elements exist

    def _build_topbar(self):
        top = tk.Frame(self, bg=BG2, pady=12, padx=16)
        top.pack(fill="x")

        # Title
        tk.Label(top, text="MEMORY SIMULATOR", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=(0, 20))

        # Memory Tech Toggle (MVT / MFT)
        mem_seg = tk.Frame(top, bg=BORDER)
        mem_seg.pack(side="left", padx=(0, 16))
        tk.Label(mem_seg, text="Tech: ", bg=BG2, fg=TXT2, font=("Segoe UI", 10)).pack(side="left", padx=4)
        
        self._mem_btns = {}
        for label, val in [("MVT", "mvt"), ("MFT", "mft")]:
            b = tk.Button(mem_seg, text=label, font=("Segoe UI", 10, "bold"),
                          bd=0, padx=12, pady=6, cursor="hand2",
                          command=lambda v=val: self._set_mem(v))
            b.pack(side="left")
            self._mem_btns[val] = b
            
        # Algorithm Toggle
        algo_seg = tk.Frame(top, bg=BORDER)
        algo_seg.pack(side="left", padx=(0, 16))
        self._algo_btns = {}
        for label, val in [("RR", "rr"), ("FCFS", "fcfs"), ("SJF", "sjf")]:
            b = tk.Button(algo_seg, text=label, font=("Segoe UI", 10, "bold"),
                          bd=0, padx=12, pady=6, cursor="hand2",
                          command=lambda v=val: self._set_algo(v))
            b.pack(side="left")
            self._algo_btns[val] = b

        # Quantum (Build but DO NOT pack yet - _update_toggles handles packing)
        self._quantum_frame = tk.Frame(top, bg=BG2)
        tk.Label(self._quantum_frame, text="Q =", bg=BG2, fg=TXT2, font=("Segoe UI", 10)).pack(side="left")
        self.quantum_var = tk.StringVar(value="5")
        self._quantum_entry = tk.Entry(
            self._quantum_frame, textvariable=self.quantum_var,
            width=3, font=("Segoe UI", 11, "bold"),
            bg=BG, fg=ACCENT, relief="solid", highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT, bd=0, justify="center"
        )
        self._quantum_entry.pack(side="left", padx=(4, 0))

        # Compaction (Build but DO NOT pack yet - _update_toggles handles packing)
        self.compact_btn = tk.Button(
            top, text="⊞ Compaction: OFF", bg=BG, fg=TXT2, font=("Segoe UI", 10),
            bd=1, relief="solid", highlightthickness=0,
            activebackground=BG2, activeforeground=TXT,
            cursor="hand2", padx=12, pady=5, command=self._toggle_compaction
        )

        # Right side controls
        right_ctrl = tk.Frame(top, bg=BG2)
        right_ctrl.pack(side="right")

        tk.Button(
            right_ctrl, text="↺ RESET", bg=BORDER, fg=TXT, font=("Segoe UI", 10, "bold"),
            bd=0, cursor="hand2", padx=14, pady=6, command=self._reset
        ).pack(side="left", padx=(0, 8))

        self.step_btn = tk.Button(
            right_ctrl, text="▶ STEP +1", bg=ACCENT, fg="#000", font=("Segoe UI", 10, "bold"),
            bd=0, cursor="hand2", padx=14, pady=6, command=self._step,
            activebackground="#76FF03"
        )
        self.step_btn.pack(side="left")

        self.time_lbl = tk.Label(
            right_ctrl, text="T = 0", bg=BG, fg=TXT, font=("Segoe UI", 12, "bold"),
            padx=14, pady=6, bd=1, relief="solid", highlightthickness=0, highlightbackground=BORDER
        )
        self.time_lbl.pack(side="left", padx=(16, 0))

    def _build_banner(self):
        self.banner_frame = tk.Frame(self, bg="#332B00", highlightbackground="#FFB74D", highlightthickness=1)
        self.banner_lbl = tk.Label(self.banner_frame, text="", bg="#332B00", fg="#FFD54F",
                                   font=("Segoe UI", 10, "bold"), padx=12, pady=6)
        self.banner_lbl.pack()

    def _build_content(self):
        content = tk.Frame(self, bg=BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)

        # ── Left Column: Memory ──────────────────────────────────────────────
        left_wrap = tk.Frame(content, bg=BG, width=MEM_W + 30)
        left_wrap.pack(side="left", fill="y", padx=(0, 16))
        left_wrap.pack_propagate(False)

        mem_panel = self._make_panel(left_wrap, "MEMORY MAP (256K)")
        mem_panel.pack(fill="both", expand=True)

        self.mem_canvas = tk.Canvas(
            mem_panel, bg=FREE_BG, bd=0, highlightthickness=1,
            highlightbackground=BORDER, width=MEM_W, height=MEM_H
        )
        self.mem_canvas.pack(pady=(4, 8))

        frow = tk.Frame(mem_panel, bg=BG2)
        frow.pack(fill="x")
        self.frag_lbl_title = tk.Label(frow, text="Ext. Frag:", bg=BG2, fg=TXT3, font=("Segoe UI", 9))
        self.frag_lbl_title.pack(side="left")
        
        self.frag_pct_lbl = tk.Label(frow, text="0%", bg=BG2, fg=ACCENT, font=("Segoe UI", 9, "bold"))
        self.frag_pct_lbl.pack(side="right")

        fbar_bg = tk.Frame(mem_panel, bg=BORDER, height=6, width=MEM_W)
        fbar_bg.pack(anchor="w", pady=(2, 6))
        fbar_bg.pack_propagate(False)
        self._frag_bar_bg = fbar_bg
        self.frag_bar = tk.Frame(fbar_bg, bg=ACCENT, height=6)
        self.frag_bar.place(x=0, y=0, relheight=1.0, width=0)

        self.free_lbl = tk.Label(mem_panel, text="Free: 216K", bg=BG2, fg=TXT3, font=("Segoe UI", 10))
        self.free_lbl.pack(anchor="w")

        # ── Right Column: Data ───────────────────────────────────────────────
        right = tk.Frame(content, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        # Add/Remove
        apanel = self._make_panel(right, "PROCESS MANAGEMENT")
        apanel.pack(fill="x", pady=(0, 12))
        self._build_add_proc_form(apanel)

        # Table
        tpanel = self._make_panel(right, "PROCESS TABLE")
        tpanel.pack(fill="x", pady=(0, 12))
        self._build_proc_table(tpanel)

        # Gantt
        gpanel = self._make_panel(right, "GANTT CHART")
        gpanel.pack(fill="x", pady=(0, 12))
        self.gantt_canvas = tk.Canvas(gpanel, bg=BG2, bd=0, highlightthickness=0, height=100)
        self.gantt_canvas.pack(fill="x", expand=True)
        self.gantt_canvas.bind("<Configure>", lambda e: self._render_gantt())

        # Events
        epanel = self._make_panel(right, "SYSTEM EVENTS")
        epanel.pack(fill="both", expand=True)
        self._build_event_log(epanel)

    def _build_add_proc_form(self, parent):
        row = tk.Frame(parent, bg=BG2)
        row.pack(fill="x", pady=4)

        tk.Label(row, text="Size (K):", bg=BG2, fg=TXT2, font=("Segoe UI", 10)).pack(side="left")
        self.add_mem_var = tk.StringVar(value="40")
        tk.Entry(row, textvariable=self.add_mem_var, width=6, font=("Segoe UI", 10),
                 bg=BG, fg=TXT, relief="solid", highlightbackground=BORDER,
                 highlightthickness=1, bd=0, insertbackground=TXT).pack(side="left", padx=(4, 16))

        tk.Label(row, text="Burst:", bg=BG2, fg=TXT2, font=("Segoe UI", 10)).pack(side="left")
        self.add_burst_var = tk.StringVar(value="10")
        tk.Entry(row, textvariable=self.add_burst_var, width=6, font=("Segoe UI", 10),
                 bg=BG, fg=TXT, relief="solid", highlightbackground=BORDER,
                 highlightthickness=1, bd=0, insertbackground=TXT).pack(side="left", padx=(4, 16))

        tk.Button(row, text="+ ADD JOB", bg=ACCENT2, fg=TXT, font=("Segoe UI", 9, "bold"),
                  bd=0, padx=12, pady=4, cursor="hand2", command=self._add_process).pack(side="left", padx=(0, 24))

        tk.Frame(row, bg=BORDER, width=2, height=24).pack(side="left", padx=(0, 24))

        tk.Label(row, text="Job ID:", bg=BG2, fg=TXT2, font=("Segoe UI", 10)).pack(side="left")
        self.remove_id_var = tk.StringVar(value="")
        tk.Entry(row, textvariable=self.remove_id_var, width=5, font=("Segoe UI", 10),
                 bg=BG, fg=TXT, relief="solid", highlightbackground=BORDER,
                 highlightthickness=1, bd=0, insertbackground=TXT).pack(side="left", padx=(4, 10))
                 
        tk.Button(row, text="REMOVE", bg="#8B0000", fg=TXT, font=("Segoe UI", 9, "bold"),
                  bd=0, padx=12, pady=4, cursor="hand2", command=self._remove_process).pack(side="left")

        self.add_status_lbl = tk.Label(parent, text="", bg=BG2, fg=TXT3, font=("Segoe UI", 9))
        self.add_status_lbl.pack(anchor="w", pady=(4, 0))

    def _make_panel(self, parent, title):
        outer = tk.Frame(parent, bg=BORDER)
        inner = tk.Frame(outer, bg=BG2, padx=12, pady=10)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(inner, text=title, bg=BG2, fg=TXT3, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 8))
        
        # Monkey patch pack to use inner container
        def _pack(**kw): outer.pack(**kw)
        inner.pack = _pack
        return inner

    def _build_proc_table(self, parent):
        cols   = ("Job", "Mem", "Burst", "Rem", "Status", "Addr")
        widths = (60, 60, 60, 60, 110, 70)
        
        self.proc_tree = ttk.Treeview(parent, columns=cols, show="headings",
                                      height=len(JOBS), selectmode="none")
        for col, w in zip(cols, widths):
            self.proc_tree.heading(col, text=col, anchor="w")
            self.proc_tree.column(col, width=w, minwidth=w, stretch=False, anchor="w")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=BG, fieldbackground=BG,
                        foreground=TXT, rowheight=26, font=("Segoe UI", 10), borderwidth=0)
        style.configure("Treeview.Heading", background=BORDER, foreground=TXT2,
                        font=("Segoe UI", 10, "bold"), relief="flat", borderwidth=0)
        style.map("Treeview", background=[("selected", BG)], foreground=[("selected", TXT)])

        for st, (bg, fg) in STATUS_STYLE.items():
            self.proc_tree.tag_configure(st, background=bg, foreground=fg)
        self.proc_tree.pack(fill="x")

    def _build_event_log(self, parent):
        wrap = tk.Frame(parent, bg=BG, highlightbackground=BORDER, highlightthickness=1)
        wrap.pack(fill="both", expand=True)

        sb = tk.Scrollbar(wrap, width=14)
        sb.pack(side="right", fill="y")

        self.event_text = tk.Text(wrap, bg=BG, fg=TXT2, bd=0, font=("Consolas", 10),
                                  height=6, highlightthickness=0, state="disabled",
                                  wrap="word", yscrollcommand=sb.set, padx=8, pady=8)
        sb.config(command=self.event_text.yview)
        self.event_text.pack(fill="both", expand=True)

        for key, col in EVENT_COLORS.items():
            self.event_text.tag_configure(key, foreground=col)

    # ── UI Actions ───────────────────────────────────────────────────────────
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
        self.add_status_lbl.config(text=msg, fg="#E57373" if error else ACCENT)
        self.after(3500, lambda: self.add_status_lbl.config(text=""))

    def _rebuild_gantt_height(self):
        gh = max(40, len(self.sim.base_jobs) * (GANTT_H + 8))
        self.gantt_canvas.config(height=gh)

    def _update_toggles(self):
        val = self.algo_var.get()
        for v, b in self._algo_btns.items():
            b.config(bg=TXT if v == val else BG, fg=BG if v == val else TXT2)
        
        # Safely pack/unpack UI elements that exist
        if hasattr(self, "_quantum_frame"):
            if val == "rr":
                self._quantum_frame.pack(side="left", padx=(0, 16))
            else:
                self._quantum_frame.pack_forget()

        mem = self.mem_var.get()
        for v, b in self._mem_btns.items():
            b.config(bg=ACCENT if v == mem else BG, fg="#000" if v == mem else TXT2)
            
        if hasattr(self, "compact_btn") and hasattr(self, "frag_lbl_title"):
            if mem == "mft":
                self.compact_btn.pack_forget()
                self.frag_lbl_title.config(text="Int. Frag:")
            else:
                self.compact_btn.pack(side="left", padx=(0, 16))
                self.frag_lbl_title.config(text="Ext. Frag:")

    def _set_algo(self, val):
        self.algo_var.set(val)
        self._update_toggles()
        self._reset()

    def _set_mem(self, val):
        self.mem_var.set(val)
        self.sim.mem_tech = val
        self._update_toggles()
        self._reset()

    def _toggle_compaction(self):
        self.sim.compaction_on = not self.sim.compaction_on
        state = "ON" if self.sim.compaction_on else "OFF"
        self.compact_btn.config(
            bg=ACCENT2 if self.sim.compaction_on else BG,
            fg=TXT if self.sim.compaction_on else TXT2,
            text=f"⊞ Compaction: {state}"
        )
        self._reset()

    def _reset(self):
        self.sim.reset()
        self._hide_banner()
        self.step_btn.config(state="normal")
        self._rebuild_gantt_height()
        self._render()

    def _step(self):
        try:
            q = int(self.quantum_var.get().strip())
            q = max(1, q)
        except ValueError:
            self.quantum_var.set("5")
            q = 5

        msg = self.sim.step(self.algo_var.get(), quantum=q)
        if msg: self._show_banner(msg)
        if self.sim.finished: self.step_btn.config(state="disabled")
        self._render()

    def _show_banner(self, msg):
        self.banner_lbl.config(text=f"⬇ {msg}")
        self.banner_frame.pack(fill="x", padx=16, pady=(0, 4))
        if self._banner_after:
            self.after_cancel(self._banner_after)
        self._banner_after = self.after(3000, self._hide_banner)

    def _hide_banner(self):
        self.banner_frame.pack_forget()
        self._banner_after = None

    # ── Rendering ────────────────────────────────────────────────────────────
    def _render(self):
        self.time_lbl.config(text=f"T = {self.sim.time}")
        self._render_mem()
        self._render_proc_table()
        self._render_gantt()
        self._render_events()

    def _render_mem(self):
        c = self.mem_canvas
        c.delete("all")
        W, H = MEM_W, MEM_H

        # OS block is always present
        segs = [{"size": OS_SIZE, "label": f"OS\n{OS_SIZE}K", "bg": OS_BG, "fg": OS_FG}]

        if self.sim.mem_tech == "mvt":
            in_mem = sorted([p for p in self.sim.procs if p["addr"] >= 0], key=lambda p: p["addr"])
            cur = OS_SIZE
            for p in in_mem:
                if p["addr"] > cur:
                    gap = p["addr"] - cur
                    segs.append({"size": gap, "label": f"Free\n{gap}K", "bg": FREE_BG, "fg": FREE_FG})
                segs.append({"size": p["mem"], "label": f"J{p['id']}\n{p['mem']}K", 
                             "bg": PCOLS[p["ci"]], "fg": "#FFF"})
                cur = p["addr"] + p["mem"]
            if cur < TOTAL:
                gap = TOTAL - cur
                segs.append({"size": gap, "label": f"Free\n{gap}K", "bg": FREE_BG, "fg": FREE_FG})
        else:
            # Render MFT partitions
            for part in self.sim.partitions:
                if part["job"] is not None:
                    job = next(j for j in self.sim.procs if j["id"] == part["job"])
                    segs.append({"size": job["mem"], "label": f"J{job['id']}\n{job['mem']}K",
                                 "bg": PCOLS[job["ci"]], "fg": "#FFF", "part_outline": True})
                    
                    int_frag = part["size"] - job["mem"]
                    if int_frag > 0:
                        segs.append({"size": int_frag, "label": f"Frag\n{int_frag}K", 
                                     "bg": FRAG_BG, "fg": "#E0B0FF", "is_frag": True})
                else:
                    segs.append({"size": part["size"], "label": f"P{part['id']} Free\n{part['size']}K",
                                 "bg": FREE_BG, "fg": FREE_FG, "part_outline": True})

        y = H
        for seg in segs:
            h = max(int(seg["size"] / TOTAL * H), 2)
            y -= h
            
            # Draw segment
            outline = TXT2 if seg.get("part_outline") else BORDER
            width   = 1.5 if seg.get("part_outline") else 0.5
            if seg.get("is_frag"): outline = ""
            
            c.create_rectangle(0, y, W, y + h, fill=seg["bg"], outline=outline, width=width)
            
            lines = seg["label"].split("\n")
            mid_y = y + h // 2
            offset = 8 if len(lines) > 1 and h >= 32 else 0
            
            if h >= 18:
                c.create_text(W // 2, mid_y - offset, text=lines[0], fill=seg["fg"],
                              font=("Segoe UI", 10, "bold"))
                if offset:
                    c.create_text(W // 2, mid_y + offset + 2, text=lines[1], fill=seg["fg"],
                                  font=("Segoe UI", 8))

        # Frag Label
        frag = self.sim.get_fragmentation()
        if self.sim.mem_tech == "mvt":
            bar_w = int(MEM_W * frag / 100)
            self.frag_pct_lbl.config(text=f"{frag}%")
        else:
            # Internal fragmentation max context is 216K
            bar_w = int(MEM_W * (frag / (TOTAL - OS_SIZE)))
            self.frag_pct_lbl.config(text=f"{frag}K")
            
        self.frag_bar.place(x=0, y=0, relheight=1.0, width=bar_w)

        fk = self.sim.free_k()
        if self.sim.mem_tech == "mvt":
            hn = len(self.sim.holes)
            self.free_lbl.config(text=f"Free: {fk}K ({hn} hole{'s' if hn != 1 else ''})")
        else:
            free_parts = sum(1 for p in self.sim.partitions if p["job"] is None)
            self.free_lbl.config(text=f"Free: {fk}K ({free_parts} empty partitions)")

    def _render_proc_table(self):
        n = len(self.sim.procs)
        self.proc_tree.config(height=max(3, min(n, 12)))
        for row in self.proc_tree.get_children(): self.proc_tree.delete(row)

        for p in self.sim.procs:
            addr = f"{p['addr']}K" if p["addr"] >= 0 else "—"
            if self.sim.mem_tech == "mft" and p["part_id"]:
                addr += f" (P{p['part_id']})"
                
            self.proc_tree.insert(
                "", "end",
                values=(f"● J{p['id']}", f"{p['mem']}K", p["burst"], p["remaining"], p["status"].upper(), addr),
                tags=(p["status"],)
            )

    def _render_gantt(self):
        c = self.gantt_canvas
        c.delete("all")
        W = c.winfo_width()
        if W <= 1: return
        
        maxT    = max(self.sim.time, 1)
        lbl_w   = 50
        track_w = W - lbl_w - 16
        y0      = 10

        # Time markers
        for t in range(0, maxT + 1, 5):
            x = lbl_w + int(t / maxT * track_w)
            c.create_text(x, y0, text=str(t), fill=TXT3, font=("Segoe UI", 8), anchor="s")

        for idx, p in enumerate(self.sim.procs):
            y = y0 + 10 + idx * (GANTT_H + 8)
            c.create_text(lbl_w - 8, y + GANTT_H // 2, text=f"JOB {p['id']}", fill=TXT2,
                          font=("Segoe UI", 9, "bold"), anchor="e")
            c.create_rectangle(lbl_w, y, lbl_w + track_w, y + GANTT_H, fill=BG, outline=BORDER)
            
            ticks = self.sim.gantt[p["id"]]
            if ticks:
                cell_w = track_w / maxT
                for ti, tick in enumerate(ticks):
                    x0 = lbl_w + int(ti * cell_w)
                    x1 = lbl_w + int((ti + 1) * cell_w)
                    if tick == "run":
                        c.create_rectangle(x0, y, x1, y + GANTT_H, fill=PCOLS[p["ci"]], outline="")

    def _render_events(self):
        self.event_text.config(state="normal")
        self.event_text.delete("1.0", "end")
        for msg, color in self.sim.events:
            self.event_text.insert("end", "> " + msg + "\n", color)
        self.event_text.config(state="disabled")


# ── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    root.title("MVT/MFT Memory Simulator")
    root.minsize(960, 720)
    root.configure(bg=BG)
    app = App(root)
    app.pack(fill="both", expand=True)
    root.mainloop()
