import tkinter as tk
from tkinter import ttk, messagebox

# ── Colors ───────────────────────────────────────────────────────────────────
BG          = "#1E1E1E"
BG2         = "#2A2A2A"
BG3         = "#333333"
TEXT        = "#E8E6E3"
TEXT2       = "#A8A6A3"
TEXT3       = "#6B6967"
BORDER      = "#3A3A3A"
BORDER2     = "#444444"
ACCENT      = "#A855F7" 
PURPLE_LIGHT= "#E0B3FF" 
PURPLE_DARK = "#3B0D66"  
RED         = "#993C1D"
RED_LIGHT   = "#F5C4B3"
RED_DARK    = "#4A1B0C"
GREEN       = "#0F6E56"
ORANGE      = "#D85A30"
BAR_GRAY    = "#555550"
BAR_GREEN   = "#1D9E75"
WHITE       = "#FFFFFF"
YELLOW      = "#C8A84B"

DESCS = {
    "fifo":   "FIFO — the page that was loaded first is replaced first. Simple but can worsen with more frames (Belady's anomaly).",
    "lru":    "LRU — replaces the page unused for the longest time. Better than FIFO in practice; no Belady's anomaly.",
    "opt":    "OPT (optimal/MIN) — replaces the page not needed for the longest future time. Theoretical best; used as a benchmark.",
    "second": "Second chance (clock) — FIFO with a reference bit. A page with bit=1 gets a second chance; its bit is cleared and it moves to the back of the queue.",
    "lfu":    "LFU (Least Frequently Used) — keeps a running count of references per page. The page with the lowest count is replaced. FIFO breaks ties.",
    "mfu":    "MFU (Most Frequently Used) — replaces the page with the highest count, arguing the least-used page was just brought in and still needs to be used.",
}

REF_STRINGS = {
    "Classic (7,0,1,2,0,3...)":       [7,0,1,2,0,3,0,4,2,3,0,3,2,1,2,0,1,7,0,1],
    "Belady demo (1,2,3,4,1,2,5...)": [1,2,3,4,1,2,5,1,2,3,4,5],
    "Thrashing demo":                  [0,1,2,3,0,1,4,0,1,2,3,4],
}

# ── Algorithms ────────────────────────────────────────────────────────────────
def compute_fifo(refs, n):
    mem, queue, steps = [], [], []
    for p in refs:
        hit = p in mem; victim = None; new_mem = list(mem)
        if not hit:
            if len(mem) < n: new_mem.append(p); queue.append(p)
            else:
                victim = queue.pop(0)
                new_mem[new_mem.index(victim)] = p; queue.append(p)
        mem = list(new_mem)
        steps.append({"page": p, "hit": hit, "victim": victim, "mem": list(mem), "counts": None})
    return steps

def compute_lru(refs, n):
    mem, recent, steps = [], [], []
    for p in refs:
        hit = p in mem; victim = None; new_mem = list(mem)
        if hit: recent = [x for x in recent if x != p]; recent.append(p)
        else:
            if len(mem) < n: new_mem.append(p); recent.append(p)
            else:
                victim = recent.pop(0)
                new_mem[new_mem.index(victim)] = p; recent.append(p)
        mem = list(new_mem)
        steps.append({"page": p, "hit": hit, "victim": victim, "mem": list(mem), "counts": None})
    return steps

def compute_opt(refs, n):
    mem, steps = [], []
    for i, p in enumerate(refs):
        hit = p in mem; victim = None; new_mem = list(mem)
        if not hit:
            if len(mem) < n: new_mem.append(p)
            else:
                farthest, vi = -1, -1; future = refs[i+1:]
                for j, pg in enumerate(mem):
                    try: nxt = future.index(pg)
                    except ValueError: vi = j; break
                    if nxt > farthest: farthest = nxt; vi = j
                victim = new_mem[vi]; new_mem[vi] = p
        mem = list(new_mem)
        steps.append({"page": p, "hit": hit, "victim": victim, "mem": list(mem), "counts": None})
    return steps

def compute_second(refs, n):
    mem, bits, ptr, steps = [], [], 0, []
    for p in refs:
        hit = p in mem; victim = None; new_mem = list(mem); new_bits = list(bits)
        if hit: new_bits[mem.index(p)] = 1
        else:
            if len(mem) < n: new_mem.append(p); new_bits.append(1)
            else:
                while new_bits[ptr] == 1: new_bits[ptr] = 0; ptr = (ptr+1)%n
                victim = new_mem[ptr]; new_mem[ptr] = p; new_bits[ptr] = 1; ptr = (ptr+1)%n
        mem = list(new_mem); bits = list(new_bits)
        steps.append({"page": p, "hit": hit, "victim": victim, "mem": list(mem), "counts": None, "bits": list(bits)})
    return steps

def compute_counting(refs, n, mode):
    mem, counts, arrival, steps = [], {}, [], []
    for i, p in enumerate(refs):
        counts[p] = counts.get(p, 0) + 1
        hit = p in mem; victim = None; new_mem = list(mem)
        if not hit:
            if len(mem) < n: new_mem.append(p); arrival.append(p)
            else:
                def sort_key(pg, _counts=counts, _arrival=arrival, _mode=mode):
                    cnt = _counts.get(pg, 0)
                    arr = _arrival.index(pg) if pg in _arrival else 999
                    return (cnt if _mode == "lfu" else -cnt, arr)
                victim = sorted(mem, key=sort_key)[0]
                new_mem[new_mem.index(victim)] = p
                arrival = [x for x in arrival if x != victim]; arrival.append(p)
        mem = list(new_mem)
        counts_snap = {pg: counts.get(pg, 0) for pg in sorted(set(refs[:i+1]))}
        steps.append({"page": p, "hit": hit, "victim": victim, "mem": list(mem),
                      "counts": dict(counts_snap), "victim_page": victim})
    return steps

def compute(algo, refs, frames):
    if algo == "fifo":   return compute_fifo(refs, frames)
    if algo == "lru":    return compute_lru(refs, frames)
    if algo == "opt":    return compute_opt(refs, frames)
    if algo == "second": return compute_second(refs, frames)
    if algo == "lfu":    return compute_counting(refs, frames, "lfu")
    return compute_counting(refs, frames, "mfu")

# ── App ───────────────────────────────────────────────────────────────────────
class PageReplacementApp(tk.Frame):
    CELL = 34
    GAP  = 4

    def __init__(self, master):
        super().__init__(master, bg=BG)

        self.algo         = "fifo"
        self.refs         = REF_STRINGS["Classic (7,0,1,2,0,3...)"]
        self.frames_count = 3
        self.steps        = []
        self.cur          = -1
        self._timer       = None
        self._playing     = False

        self._build_ui()
        self._compute_and_reset()

    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Top fixed panel (controls, tabs, legend, info) ───────────────────
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=18, pady=(14, 0))

        tk.Label(top, text="Page replacement algorithm simulator",
                 bg=BG, fg=TEXT, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(top, text="Step through FIFO, LRU, OPT, second chance, LFU, and MFU",
                 bg=BG, fg=TEXT2, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 8))

        # Algo description
        self.desc_var = tk.StringVar()
        desc_f = tk.Frame(top, bg=BG2)
        desc_f.pack(fill="x", pady=(0, 8))
        tk.Frame(desc_f, bg=ACCENT, width=3).pack(side="left", fill="y")
        tk.Label(desc_f, textvariable=self.desc_var, bg=BG2, fg=TEXT2,
                 font=("Segoe UI", 10), wraplength=680, justify="left",
                 padx=10, pady=8).pack(side="left", fill="x", expand=True)

        # ── Controls row ─────────────────────────────────────────────────────
        ctrl = tk.Frame(top, bg=BG)
        ctrl.pack(fill="x", pady=(0, 4))
        ctrl.columnconfigure(0, weight=3)
        ctrl.columnconfigure(1, weight=1)
        ctrl.columnconfigure(2, weight=0)

        # Reference string preset dropdown
        lf0 = tk.Frame(ctrl, bg=BG); lf0.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        tk.Label(lf0, text="Reference string", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.ref_var = tk.StringVar(value="Classic (7,0,1,2,0,3...)")
        self.ref_cb = ttk.Combobox(lf0, textvariable=self.ref_var,
                                   values=list(REF_STRINGS.keys()),
                                   state="readonly", font=("Segoe UI", 11))
        self.ref_cb.pack(fill="x")
        self.ref_cb.bind("<<ComboboxSelected>>", self._on_preset_selected)

        # Frames spinbox
        lf1 = tk.Frame(ctrl, bg=BG); lf1.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        tk.Label(lf1, text="Frames", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.frame_var = tk.IntVar(value=3)
        sb = tk.Spinbox(lf1, from_=1, to=9, textvariable=self.frame_var, width=5,
                        font=("Segoe UI", 11), bg=BG2, fg=TEXT,
                        insertbackground=TEXT, buttonbackground=BG3,
                        relief="flat", bd=1)
        sb.pack(fill="x")
        sb.bind("<FocusOut>", lambda e: self._compute_and_reset())
        sb.bind("<Return>", lambda e: self._compute_and_reset())
        self.frame_var.trace_add("write", lambda *_: self.after(100, self._compute_and_reset))

        # Reset button
        lf2 = tk.Frame(ctrl, bg=BG); lf2.grid(row=0, column=2, sticky="s")
        tk.Button(lf2, text="Reset", command=self._compute_and_reset,
                  bg=BG2, fg=TEXT, font=("Segoe UI", 10), relief="flat",
                  padx=12, pady=5, cursor="hand2",
                  activebackground=BG3, activeforeground=TEXT).pack()

        # ── Custom reference string row ───────────────────────────────────────
        custom_f = tk.Frame(top, bg=BG)
        custom_f.pack(fill="x", pady=(2, 8))

        tk.Label(custom_f, text="Custom string:", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))

        self.custom_var = tk.StringVar()
        custom_entry = tk.Entry(custom_f, textvariable=self.custom_var,
                                font=("Segoe UI", 10), bg=BG2, fg=TEXT,
                                insertbackground=TEXT, relief="flat",
                                highlightthickness=1, highlightbackground=BORDER,
                                highlightcolor=ACCENT)
        custom_entry.pack(side="left", fill="x", expand=True, ipady=4)
        custom_entry.bind("<Return>", lambda e: self._use_custom())

        tk.Label(custom_f, text="(e.g. 1,2,3,4,1,2)", bg=BG, fg=TEXT3,
                 font=("Segoe UI", 9, "italic")).pack(side="left", padx=(6, 8))

        tk.Button(custom_f, text="Use", command=self._use_custom,
                  bg=ACCENT, fg=WHITE, font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground="#8C3CD9", activeforeground=WHITE).pack(side="left")

        # ── Algorithm tabs ────────────────────────────────────────────────────
        tab_frame = tk.Frame(top, bg=BG)
        tab_frame.pack(fill="x", pady=(0, 8))
        self.tab_btns = {}
        for key, lbl in [("fifo","FIFO"),("lru","LRU"),("opt","OPT"),
                          ("second","Second chance"),("lfu","LFU"),("mfu","MFU")]:
            btn = tk.Button(tab_frame, text=lbl,
                            command=lambda k=key: self._set_algo(k),
                            font=("Segoe UI", 10), relief="flat",
                            padx=10, pady=4, cursor="hand2")
            btn.pack(side="left", padx=2)
            self.tab_btns[key] = btn
        self._style_tabs()

        # ── Legend ────────────────────────────────────────────────────────────
        leg = tk.Frame(top, bg=BG)
        leg.pack(fill="x", pady=(0, 8))
        for color, border, lbl in [
            (ACCENT,       None,   "Current reference"),
            (RED,          None,   "Page fault"),
            (GREEN,        None,   "Page hit"),
            (PURPLE_LIGHT, ACCENT, "Newly loaded"),
            (RED_LIGHT,    ORANGE, "Evicted"),
        ]:
            dot = tk.Frame(leg, bg=color, width=12, height=12,
                           highlightthickness=1 if border else 0,
                           highlightbackground=border or color)
            dot.pack(side="left", padx=(0, 3))
            dot.pack_propagate(False)
            tk.Label(leg, text=lbl, bg=BG, fg=TEXT2,
                     font=("Segoe UI", 9)).pack(side="left", padx=(0, 12))

        # ── Info box ──────────────────────────────────────────────────────────
        info_f = tk.Frame(top, bg=BG2)
        info_f.pack(fill="x", pady=(0, 8))
        tk.Frame(info_f, bg=ACCENT, width=3).pack(side="left", fill="y")
        self.info_var = tk.StringVar(value="Press step or play to begin.")
        tk.Label(info_f, textvariable=self.info_var, bg=BG2, fg=TEXT,
                 font=("Segoe UI", 10), wraplength=680, justify="left",
                 padx=10, pady=8, anchor="w").pack(side="left", fill="x", expand=True)

        # ── Scrollable simulation card ────────────────────────────────────────
        sim_outer = tk.Frame(self, bg=BG, padx=18)
        sim_outer.pack(fill="both", expand=True, pady=(0, 14))

        # Canvas + scrollbar for the whole sim card
        self._scroll_canvas = tk.Canvas(sim_outer, bg=BG, highlightthickness=0)
        vscroll = tk.Scrollbar(sim_outer, orient="vertical",
                               command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side="right", fill="y")
        self._scroll_canvas.pack(side="left", fill="both", expand=True)

        self._sim_card = tk.Frame(self._scroll_canvas, bg=BG2,
                                  highlightthickness=1, highlightbackground=BORDER)
        self._card_win = self._scroll_canvas.create_window(
            (0, 0), window=self._sim_card, anchor="nw")

        self._sim_card.bind("<Configure>", self._on_card_configure)
        self._scroll_canvas.bind("<Configure>", self._on_canvas_configure)
        # Mouse-wheel scrolling
        self._scroll_canvas.bind_all("<MouseWheel>",
            lambda e: self._scroll_canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._scroll_canvas.bind_all("<Button-4>",
            lambda e: self._scroll_canvas.yview_scroll(-1, "units"))
        self._scroll_canvas.bind_all("<Button-5>",
            lambda e: self._scroll_canvas.yview_scroll(1, "units"))

        # ── Inside sim card ───────────────────────────────────────────────────
        # Reference string row
        ref_hdr = tk.Frame(self._sim_card, bg=BG3)
        ref_hdr.pack(fill="x")
        tk.Label(ref_hdr, text="REFERENCE STRING", bg=BG3, fg=TEXT3,
                 font=("Segoe UI", 8, "bold"), pady=6, padx=12).pack(anchor="w")
        ref_cf = tk.Frame(self._sim_card, bg=BG3)
        ref_cf.pack(fill="x")
        self.ref_canvas = tk.Canvas(ref_cf, bg=BG3, height=self.CELL+8, highlightthickness=0)
        ref_xscroll = tk.Scrollbar(ref_cf, orient="horizontal", command=self.ref_canvas.xview)
        self.ref_canvas.configure(xscrollcommand=ref_xscroll.set)
        self.ref_canvas.pack(fill="x", padx=10, pady=(0, 2))
        ref_xscroll.pack(fill="x", padx=10, pady=(0, 6))

        tk.Frame(self._sim_card, bg=BORDER, height=1).pack(fill="x")

        # Frames area
        fr_hdr = tk.Frame(self._sim_card, bg=BG2)
        fr_hdr.pack(fill="x")
        tk.Label(fr_hdr, text="FRAMES AT EACH STEP", bg=BG2, fg=TEXT3,
                 font=("Segoe UI", 8, "bold"), pady=6, padx=12).pack(anchor="w")
        fr_cf = tk.Frame(self._sim_card, bg=BG2)
        fr_cf.pack(fill="x")
        self.frame_canvas = tk.Canvas(fr_cf, bg=BG2, highlightthickness=0)
        fr_xscroll = tk.Scrollbar(fr_cf, orient="horizontal", command=self.frame_canvas.xview)
        self.frame_canvas.configure(xscrollcommand=fr_xscroll.set)
        self.frame_canvas.pack(fill="x", padx=10, pady=(0, 2))
        fr_xscroll.pack(fill="x", padx=10, pady=(0, 6))

        # Tally area (LFU/MFU) — single wrapper, shown/hidden via pack/pack_forget
        self._tally_wrapper = tk.Frame(self._sim_card, bg=BG2)
        tk.Frame(self._tally_wrapper, bg=BORDER, height=1).pack(fill="x")
        self.tally_label_var = tk.StringVar(value="REFERENCE COUNTS")
        tk.Label(self._tally_wrapper, textvariable=self.tally_label_var, bg=BG2, fg=TEXT3,
                 font=("Segoe UI", 8, "bold"), pady=6, padx=12).pack(anchor="w")
        self.tally_inner = tk.Frame(self._tally_wrapper, bg=BG2)
        self.tally_inner.pack(fill="x", padx=12, pady=(0, 8))
        # Do NOT pack _tally_wrapper here; _render() handles it

        tk.Frame(self._sim_card, bg=BORDER, height=1).pack(fill="x")

        # Stats row
        stats_row = tk.Frame(self._sim_card, bg=BG3)
        stats_row.pack(fill="x")
        self.stat_faults = tk.StringVar(value="0")
        self.stat_hits   = tk.StringVar(value="0")
        self.stat_rate   = tk.StringVar(value="0%")
        for var, lbl in [(self.stat_faults, "Page faults"),
                         (self.stat_hits,   "Hits"),
                         (self.stat_rate,   "Fault rate")]:
            f = tk.Frame(stats_row, bg=BG3)
            f.pack(side="left", expand=True)
            tk.Label(f, textvariable=var, bg=BG3, fg=TEXT,
                     font=("Segoe UI", 16, "bold"), pady=8).pack()
            tk.Label(f, text=lbl, bg=BG3, fg=TEXT2,
                     font=("Segoe UI", 9)).pack(pady=(0, 6))

        tk.Frame(self._sim_card, bg=BORDER, height=1).pack(fill="x")

        # Step controls
        step_row = tk.Frame(self._sim_card, bg=BG2)
        step_row.pack(fill="x", padx=10, pady=8)
        btn_kw = dict(bg=BG3, fg=TEXT, font=("Segoe UI", 10), relief="flat",
                      padx=10, pady=4, cursor="hand2",
                      activebackground=BORDER2, activeforeground=TEXT)
        tk.Button(step_row, text="← Prev", command=self._prev, **btn_kw).pack(side="left", padx=2)
        self.play_btn = tk.Button(step_row, text="▶ Play", command=self._toggle_play,
                                  bg=ACCENT, fg=WHITE, font=("Segoe UI", 10, "bold"),
                                  relief="flat", padx=12, pady=4, cursor="hand2",
                                  activebackground="#8C3CD9", activeforeground=WHITE)
        self.play_btn.pack(side="left", padx=2)
        tk.Button(step_row, text="Next →", command=self._next, **btn_kw).pack(side="left", padx=2)
        self.step_label = tk.Label(step_row, text="Step 0 / 0", bg=BG2, fg=TEXT2,
                                   font=("Segoe UI", 10))
        self.step_label.pack(side="left", padx=8)

        # Combobox style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=BG2, background=BG2,
                        foreground=TEXT, selectbackground=BG3,
                        selectforeground=TEXT, arrowcolor=TEXT2, relief="flat")
        style.map("TCombobox", fieldbackground=[("readonly", BG2)],
                  foreground=[("readonly", TEXT)])

    # ── Scroll region management ──────────────────────────────────────────────
    def _on_card_configure(self, event):
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._scroll_canvas.itemconfig(self._card_win, width=event.width)

    # ── Tab styling ───────────────────────────────────────────────────────────
    def _style_tabs(self):
        for key, btn in self.tab_btns.items():
            if key == self.algo:
                btn.configure(bg=BG3, fg=TEXT)
            else:
                btn.configure(bg=BG, fg=TEXT2)

    # ── Custom reference string ───────────────────────────────────────────────
    def _on_preset_selected(self, event=None):
        self.custom_var.set("")          # clear custom field on preset change
        self._compute_and_reset()

    def _use_custom(self):
        raw = self.custom_var.get().strip()
        if not raw:
            return
        try:
            parsed = [int(x.strip()) for x in raw.replace(" ", ",").split(",") if x.strip()]
            if not parsed:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid input",
                                 "Enter comma-separated integers, e.g.  1, 2, 3, 4, 1, 2")
            return
        self._stop_play()
        self.refs = parsed
        self.ref_var.set("Custom")      # update dropdown label
        if "Custom" not in self.ref_cb["values"]:
            self.ref_cb["values"] = list(REF_STRINGS.keys()) + ["Custom"]
        self.steps = compute(self.algo, self.refs, self.frames_count)
        self.cur = -1
        self.desc_var.set(DESCS[self.algo])
        self._render()

    # ── Core logic ────────────────────────────────────────────────────────────
    def _set_algo(self, algo):
        self.algo = algo
        self._style_tabs()
        self.desc_var.set(DESCS[algo])
        self._compute_and_reset()

    def _compute_and_reset(self):
        self._stop_play()
        key = self.ref_var.get()
        if key != "Custom":
            self.refs = REF_STRINGS.get(key, REF_STRINGS["Classic (7,0,1,2,0,3...)"])
        try:
            fc = int(self.frame_var.get())
        except Exception:
            fc = 3
        self.frames_count = max(1, min(9, fc))
        self.steps = compute(self.algo, self.refs, self.frames_count)
        self.cur = -1
        self.desc_var.set(DESCS[self.algo])
        self._render()

    def _render(self):
        is_counting = self.algo in ("lfu", "mfu")

        if is_counting:
            self._tally_wrapper.pack(fill="x")
        else:
            self._tally_wrapper.pack_forget()

        self._draw_ref_cells()
        self._draw_frame_grid()
        if is_counting and self.cur >= 0:
            self._draw_tally()
        self._update_info()
        self._update_stats()

    # ── Canvas drawing ────────────────────────────────────────────────────────
    def _draw_ref_cells(self):
        c = self.ref_canvas; c.delete("all")
        CELL = self.CELL; GAP = self.GAP; pad = 4
        for i, r in enumerate(self.refs):
            x = pad + i * (CELL + GAP); y = pad
            if i == self.cur:
                bg = GREEN if self.steps[self.cur]["hit"] else RED
                fg = WHITE; outline = bg
            elif self.cur >= 0 and i < self.cur:
                bg = RED if not self.steps[i]["hit"] else BG2
                fg = WHITE if not self.steps[i]["hit"] else TEXT2
                outline = RED if not self.steps[i]["hit"] else BORDER
            else:
                bg = BG2; fg = TEXT2; outline = BORDER
            c.create_rectangle(x, y, x+CELL, y+CELL, fill=bg, outline=outline, width=1)
            c.create_text(x+CELL//2, y+CELL//2, text=str(r), fill=fg,
                          font=("Segoe UI", 11, "bold"))
        total_w = pad + len(self.refs)*(CELL+GAP) + pad
        c.configure(scrollregion=(0, 0, total_w, CELL+8), height=CELL+8)

    def _draw_frame_grid(self):
        c = self.frame_canvas; c.delete("all")
        CELL = self.CELL; GAP = self.GAP; HDR = 16
        n = self.frames_count; col_w = CELL+GAP; pad = 4
        total_h = HDR + n*(CELL+GAP) + pad

        if self.cur < 0:
            x = pad
            c.create_text(x+CELL//2, HDR//2, text="—", fill=TEXT3, font=("Segoe UI", 8))
            for f in range(n):
                y = HDR + f*(CELL+GAP)
                c.create_rectangle(x, y, x+CELL, y+CELL, fill=BG3, outline=BORDER, width=1)
                c.create_text(x+CELL//2, y+CELL//2, text="—", fill=TEXT3, font=("Segoe UI", 10))
            c.configure(scrollregion=(0, 0, pad+CELL+pad, total_h), height=total_h)
            return

        for step in range(self.cur + 1):
            s = self.steps[step]; x = pad + step*col_w
            c.create_text(x+CELL//2, HDR//2, text=str(step+1), fill=TEXT3, font=("Segoe UI", 8))
            for f in range(n):
                y = HDR + f*(CELL+GAP)
                val = s["mem"][f] if f < len(s["mem"]) else None
                if val is None:
                    bg = BG3; fg = TEXT3; outline = BORDER; lbl = ""
                elif step == self.cur and not s["hit"] and val == s["page"]:
                    bg = PURPLE_LIGHT; fg = PURPLE_DARK; outline = ACCENT; lbl = str(val)
                elif step == self.cur and val == s.get("victim") and s["victim"] is not None:
                    bg = RED_LIGHT; fg = RED_DARK; outline = ORANGE; lbl = str(val)
                else:
                    bg = BG3; fg = TEXT; outline = BORDER; lbl = str(val)
                c.create_rectangle(x, y, x+CELL, y+CELL, fill=bg, outline=outline, width=1)
                c.create_text(x+CELL//2, y+CELL//2, text=lbl, fill=fg,
                              font=("Segoe UI", 11, "bold"))

        total_w = pad + (self.cur+1)*col_w + pad
        c.configure(scrollregion=(0, 0, total_w, total_h), height=total_h)

    def _draw_tally(self):
        for w in self.tally_inner.winfo_children():
            w.destroy()
        s = self.steps[self.cur]
        counts = s.get("counts") or {}
        if not counts: return

        max_count = max(counts.values(), default=1) or 1
        self.tally_label_var.set(
            "REFERENCE COUNTS (lowest = victim)" if self.algo == "lfu"
            else "REFERENCE COUNTS (highest = victim)")

        BAR_MAX_W = 300
        for pg in sorted(counts.keys()):
            cnt = counts[pg]
            in_mem   = pg in s["mem"]
            is_victim = pg == s.get("victim") and not s["hit"]
            is_cur    = pg == s["page"]

            row = tk.Frame(self.tally_inner, bg=BG2)
            row.pack(fill="x", pady=2)

            pg_box = tk.Frame(row, bg=PURPLE_LIGHT if is_cur else BG3,
                              width=28, height=28, highlightthickness=1,
                              highlightbackground=ACCENT if is_cur else BORDER)
            pg_box.pack(side="left", padx=(0, 6))
            pg_box.pack_propagate(False)
            tk.Label(pg_box, text=str(pg),
                     bg=PURPLE_LIGHT if is_cur else BG3,
                     fg=PURPLE_DARK if is_cur else TEXT,
                     font=("Segoe UI", 10, "bold")).place(relx=0.5, rely=0.5, anchor="center")

            bar_wrap = tk.Frame(row, bg=BG3, height=20, highlightthickness=1,
                                highlightbackground=BORDER)
            bar_wrap.pack(side="left", fill="x", expand=True, padx=(0, 6))
            bar_wrap.pack_propagate(False)

            bar_color = (ORANGE   if is_victim else
                         BAR_GREEN if is_cur and not is_victim else
                         ACCENT   if in_mem else BAR_GRAY)
            text_col = PURPLE_DARK if in_mem and not is_victim else "#CCCCCC"
            bar_w = max(4, int((cnt / max_count) * BAR_MAX_W))

            bar = tk.Frame(bar_wrap, bg=bar_color, height=20)
            bar.place(x=0, y=0, width=bar_w, height=20)
            tk.Label(bar, text="■"*cnt, bg=bar_color, fg=text_col,
                     font=("Segoe UI", 8)).place(x=4, y=2)

            tk.Label(row, text=str(cnt), bg=BG2, fg=TEXT2,
                     font=("Segoe UI", 10), width=3, anchor="e").pack(side="left", padx=(0, 4))
            if is_victim:
                tk.Label(row, text="← evicted", bg=BG2, fg=RED,
                         font=("Segoe UI", 9, "bold")).pack(side="left")
            elif is_cur and not is_victim:
                tk.Label(row, text="← current", bg=BG2, fg=GREEN,
                         font=("Segoe UI", 9)).pack(side="left")

    def _update_info(self):
        if self.cur < 0:
            self.info_var.set("Press step or play to begin."); return
        s = self.steps[self.cur]
        if s["hit"]:
            msg = f"✓  Page {s['page']} is in memory — hit, no fault."
        elif s["victim"] is not None:
            msg = f"✗  Page fault! Page {s['page']} not in memory. Evicted page {s['victim']}."
        else:
            msg = f"✗  Page fault! Page {s['page']} loaded into empty frame."
        if self.algo == "second" and s.get("bits"):
            msg += f"  Reference bits: [{', '.join(str(b) for b in s['bits'])}]"
        if self.algo in ("lfu","mfu") and s.get("counts") and not s["hit"] and s["victim"] is not None:
            in_mem_p = [p for p in s["mem"] if p is not None]
            counts_str = ", ".join("{}({})".format(p, s["counts"].get(p, 0)) for p in in_mem_p)
            msg += f"  Counts in memory: {counts_str}."
        self.info_var.set(msg)

    def _update_stats(self):
        shown  = self.steps[:max(0, self.cur+1)]
        faults = sum(1 for st in shown if not st["hit"])
        hits   = sum(1 for st in shown if     st["hit"])
        total  = len(shown)
        self.stat_faults.set(str(faults))
        self.stat_hits.set(str(hits))
        self.stat_rate.set(f"{round(faults/total*100)}%" if total else "0%")
        self.step_label.configure(text=f"Step {max(0, self.cur+1)} / {len(self.steps)}")

    # ── Navigation ────────────────────────────────────────────────────────────
    def _next(self):
        if self.cur < len(self.steps)-1: self.cur += 1; self._render()
        else: self._stop_play()

    def _prev(self):
        self._stop_play()
        if self.cur > -1: self.cur -= 1; self._render()

    def _toggle_play(self):
        if self._playing: self._stop_play()
        else: self._start_play()

    def _start_play(self):
        self._playing = True
        self.play_btn.configure(text="⏸ Pause", bg=RED)
        self._tick()

    def _stop_play(self):
        self._playing = False
        if self._timer: self.after_cancel(self._timer); self._timer = None
        self.play_btn.configure(text="▶ Play", bg=ACCENT)

    def _tick(self):
        if not self._playing: return
        if self.cur < len(self.steps)-1:
            self.cur += 1; self._render()
            self._timer = self.after(750, self._tick)
        else:
            self._stop_play()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Page Replacement Algorithm Simulator")
    root.minsize(720, 600)
    root.configure(bg=BG)
    app = PageReplacementApp(root)
    app.pack(fill="both", expand=True)
    root.mainloop()
    
