import tkinter as tk
from tkinter import ttk, messagebox

# ── Colors ───────────────────────────────────────────────────────────────────
BG          = "#0a0a0a"
BG2         = "#141414"
BG3         = "#2a2a2a"
TEXT        = "#FFFFFF"
TEXT2       = "#A8A6A3"
TEXT3       = "#6B6967"
BORDER      = "#3A3A3A"
BORDER2     = "#444444"
BLUE_LIGHT  = "#B5D4F4"
BLUE_DARK   = "#042C53"

# Theme Colors
MAGENTA     = "#A855F7"  
MAGENTA_H   = "#B875FA" 
CYAN        = "#06B6D4"  
FAULT_COLOR = "#D946EF"  
FAULT_COLOR_H = "#E879F9"  
ORANGE      = "#F97316"  
BAR_GRAY    = "#3F3F46"

# ── Brief Descriptions ───────────────────────────────────────────────────────
DESCS = {
    "fifo":   "FIFO: Replaces the oldest loaded page. Simple, but susceptible to Belady's anomaly.",
    "lru":    "LRU: Replaces the page unused for the longest time. Reliable; no Belady's anomaly.",
    "opt":    "OPT: Replaces the page not needed for the longest future time. Theoretical benchmark.",
    "second": "Second Chance: FIFO with a reference bit. Pages with bit=1 get skipped and reset.",
    "lfu":    "LFU: Replaces the page with the lowest reference count. FIFO breaks ties.",
    "mfu":    "MFU: Replaces the page with the highest reference count.",
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
    CELL = 42
    GAP  = 6

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
        self._apply_stealth_scrollbars()
        self._compute_and_reset()

    def _create_round_rect(self, canvas, x1, y1, x2, y2, radius=8, **kwargs):
        points = [
            x1+radius, y1,
            x1+radius, y1, x2-radius, y1, x2-radius, y1,
            x2, y1, x2, y1+radius, x2, y1+radius,
            x2, y2-radius, x2, y2-radius, x2, y2,
            x2-radius, y2, x2-radius, y2, x1+radius, y2,
            x1+radius, y2, x1, y2, x1, y2-radius,
            x1, y2-radius, x1, y1+radius, x1, y1+radius,
            x1, y1
        ]
        return canvas.create_polygon(points, **kwargs, smooth=True)

    def _bind_hover(self, btn, normal_bg, hover_bg, normal_fg=TEXT, hover_fg=TEXT):
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg, fg=hover_fg))
        btn.bind("<Leave>", lambda e: btn.config(bg=normal_bg, fg=normal_fg))

    def _apply_stealth_scrollbars(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TScrollbar", gripcount=0, background=BORDER, darkcolor=BG, lightcolor=BG,
                        troughcolor=BG, bordercolor=BG, arrowcolor=TEXT2, relief="flat")
        style.map("TScrollbar", background=[('active', BORDER2)])
        style.configure("TCombobox", fieldbackground=BG, background=BG, foreground=TEXT, selectbackground=MAGENTA, 
                        selectforeground=BG, arrowcolor=TEXT2, relief="flat", bordercolor=BORDER, lightcolor=BG, darkcolor=BG)
        style.map("TCombobox", fieldbackground=[("readonly", BG)], foreground=[("readonly", TEXT)])

    def _build_ui(self):
        split = tk.Frame(self, bg=BG)
        split.pack(fill="both", expand=True)

        # ─── LEFT SIDEBAR ────────────────────────────────────────────────────
        sidebar = tk.Frame(split, bg=BG2, width=320, highlightthickness=1, highlightbackground=BORDER)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        hdr_frame = tk.Frame(sidebar, bg=BG2)
        hdr_frame.pack(fill="x", padx=20, pady=(25, 20))
        tk.Label(hdr_frame, text="Page Replacement", bg=BG2, fg=MAGENTA, font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(hdr_frame, text="Simulator", bg=BG2, fg=TEXT2, font=("Segoe UI", 13, "bold")).pack(anchor="w")

        algo_outer = tk.Frame(sidebar, bg=BORDER)
        algo_outer.pack(fill="x", padx=20, pady=(0, 20))
        
        self.tab_btns = {}
        algos = [("fifo", "FIFO"), ("lru", "LRU"), ("opt", "OPT"), ("second", "Second"), ("lfu", "LFU"), ("mfu", "MFU")]

        for i, (key, lbl) in enumerate(algos):
            btn = tk.Button(algo_outer, text=lbl, bd=0, relief="flat", cursor="hand2", pady=8, font=("Segoe UI", 9, "bold"))
            btn.grid(row=i//2, column=i%2, sticky="nsew", padx=1, pady=1)
            algo_outer.columnconfigure(i%2, weight=1)
            btn.configure(command=lambda k=key: self._set_algo(k))
            self.tab_btns[key] = btn
            
        self._style_tabs()

        self.desc_var = tk.StringVar()
        desc_box = tk.Frame(sidebar, bg=BG3, highlightthickness=1, highlightbackground=BORDER)
        desc_box.pack(fill="x", padx=20, pady=(0, 25))
        tk.Frame(desc_box, bg=MAGENTA, height=2).pack(fill="x", side="top")
        tk.Label(desc_box, textvariable=self.desc_var, bg=BG3, fg=TEXT, font=("Segoe UI", 9), wraplength=260, justify="left", padx=14, pady=14).pack(fill="x")

        # ── Configuration Dashboard ──
        cfg_hdr = tk.Frame(sidebar, bg=BG2)
        cfg_hdr.pack(fill="x", padx=20, pady=(0, 15))
        tk.Frame(cfg_hdr, bg=MAGENTA, width=3).pack(side="left", fill="y", pady=2)
        tk.Label(cfg_hdr, text="Configuration", bg=BG2, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)

        form_frame = tk.Frame(sidebar, bg=BG2)
        form_frame.pack(fill="x", padx=20)
        form_frame.columnconfigure(1, weight=1)

        tk.Label(form_frame, text="Preset", bg=BG2, fg=TEXT2, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=6)
        self.ref_var = tk.StringVar(value="Classic (7,0,1,2,0,3...)")
        self.ref_cb = ttk.Combobox(form_frame, textvariable=self.ref_var, values=list(REF_STRINGS.keys()), state="readonly", font=("Segoe UI", 9), width=15)
        self.ref_cb.grid(row=0, column=1, sticky="e", pady=6)
        self.ref_cb.bind("<<ComboboxSelected>>", self._on_preset_selected)

        tk.Label(form_frame, text="Frames", bg=BG2, fg=TEXT2, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=6)
        self.frame_var = tk.IntVar(value=3)
        
        stepper = tk.Frame(form_frame, bg=BG, highlightthickness=1, highlightbackground=BORDER)
        stepper.grid(row=1, column=1, sticky="e", pady=6)
        
        def adjust_frames(delta):
            val = self.frame_var.get() + delta
            if 1 <= val <= 9:
                self.frame_var.set(val)
                self._compute_and_reset()

        btn_minus = tk.Button(stepper, text="−", bg=BG, fg=TEXT2, font=("Segoe UI", 10, "bold"), bd=0, activebackground=BG3, command=lambda: adjust_frames(-1), cursor="hand2")
        btn_minus.pack(side="left", ipadx=6, ipady=1)
        self._bind_hover(btn_minus, BG, BG3, TEXT2, TEXT)

        self.lbl_frames = tk.Label(stepper, textvariable=self.frame_var, bg=BG, fg=TEXT, font=("Segoe UI", 10, "bold"), width=3)
        self.lbl_frames.pack(side="left")

        btn_plus = tk.Button(stepper, text="+", bg=BG, fg=TEXT2, font=("Segoe UI", 10, "bold"), bd=0, activebackground=BG3, command=lambda: adjust_frames(1), cursor="hand2")
        btn_plus.pack(side="left", ipadx=6, ipady=1)
        self._bind_hover(btn_plus, BG, BG3, TEXT2, TEXT)

        tk.Label(form_frame, text="Custom", bg=BG2, fg=TEXT2, font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=6)
        
        custom_wrapper = tk.Frame(form_frame, bg=BG2)
        custom_wrapper.grid(row=2, column=1, sticky="e", pady=6)
        
        self.custom_var = tk.StringVar()
        custom_entry = tk.Entry(custom_wrapper, textvariable=self.custom_var, width=14, font=("Segoe UI", 9), bg=BG, fg=TEXT, insertbackground=MAGENTA, relief="flat", highlightthickness=1, highlightbackground=BORDER)
        custom_entry.pack(side="left", ipady=3)
        custom_entry.bind("<Return>", lambda e: self._use_custom())

        apply_btn = tk.Button(custom_wrapper, text="↵", bg=BG3, fg=TEXT, font=("Segoe UI", 10, "bold"), bd=0, command=self._use_custom, cursor="hand2")
        apply_btn.pack(side="left", fill="y", padx=(4, 0), ipadx=6)
        self._bind_hover(apply_btn, BG3, BORDER2, TEXT, TEXT)

        # ─── RIGHT MAIN CONTENT ──────────────────────────────────────────────
        main_content = tk.Frame(split, bg=BG)
        main_content.pack(side="left", fill="both", expand=True)

        top_bar = tk.Frame(main_content, bg=BG, height=70)
        top_bar.pack(fill="x", padx=20, pady=(20, 10))
        top_bar.pack_propagate(False)

        self.status_frame = tk.Frame(top_bar, bg=BG, highlightthickness=1, highlightbackground=BORDER)
        self.status_frame.pack(side="left", fill="both", expand=True, padx=(0, 20))
        
        self.status_pill_bg = tk.Frame(self.status_frame, bg=BG3)
        self.status_pill_bg.pack(side="left", fill="y")
        self.status_pill = tk.Label(self.status_pill_bg, text="WAIT", bg=BG3, fg=TEXT2, font=("Segoe UI", 11, "bold"), width=8)
        self.status_pill.pack(expand=True, padx=10)

        self.info_var = tk.StringVar(value="SYSTEM IDLE  —  Awaiting trace execution.")
        tk.Label(self.status_frame, textvariable=self.info_var, bg=BG, fg=TEXT, font=("Segoe UI", 10), padx=20).pack(side="left", fill="both")

        stats_container = tk.Frame(top_bar, bg=BG)
        stats_container.pack(side="right", fill="y")

        self.stat_faults = tk.StringVar(value="0")
        self.stat_hits   = tk.StringVar(value="0")
        self.stat_total  = tk.StringVar(value="0")
        self.stat_rate   = tk.StringVar(value="0%")

        for var, lbl, col in [(self.stat_faults, "FAULTS", FAULT_COLOR), (self.stat_hits, "HITS", CYAN), (self.stat_total, "TOTAL", TEXT3), (self.stat_rate, "RATE", MAGENTA)]:
            card = tk.Frame(stats_container, bg=BG)
            card.pack(side="left", padx=(12, 12), fill="y")
            tk.Frame(card, bg=col, height=2).pack(side="top", fill="x", pady=(4, 6))
            tk.Label(card, text=" ".join(lbl), bg=BG, fg=TEXT3, font=("Segoe UI", 8, "bold")).pack(anchor="center")
            tk.Label(card, textvariable=var, bg=BG, fg=TEXT, font=("Segoe UI", 20, "bold")).pack(anchor="center")

        # ── Scrollable Canvas Area ──
        sim_outer = tk.Frame(main_content, bg=BG)
        sim_outer.pack(fill="both", expand=True, padx=20)

        self._scroll_canvas = tk.Canvas(sim_outer, bg=BG, highlightthickness=0)
        vscroll = ttk.Scrollbar(sim_outer, orient="vertical", command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side="right", fill="y")
        self._scroll_canvas.pack(side="left", fill="both", expand=True)

        self._sim_card = tk.Frame(self._scroll_canvas, bg=BG2, highlightthickness=1, highlightbackground=BORDER)
        self._card_win = self._scroll_canvas.create_window((0, 0), window=self._sim_card, anchor="nw")

        self._sim_card.bind("<Configure>", self._on_card_configure)
        self._scroll_canvas.bind("<Configure>", self._on_canvas_configure)
        self._scroll_canvas.bind_all("<MouseWheel>", lambda e: self._scroll_canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._scroll_canvas.bind_all("<Shift-MouseWheel>", lambda e: [self.ref_canvas.xview_scroll(-1*(e.delta//120), "units"), self.frame_canvas.xview_scroll(-1*(e.delta//120), "units")])

        # Ref String Row
        ref_hdr = tk.Frame(self._sim_card, bg=BG3)
        ref_hdr.pack(fill="x")
        tk.Frame(ref_hdr, bg=MAGENTA, width=3).pack(side="left", fill="y")
        tk.Label(ref_hdr, text="REFERENCE STRING", bg=BG3, fg=TEXT, font=("Segoe UI", 8, "bold"), pady=8, padx=11).pack(anchor="w", side="left")
        
        self.ref_canvas = tk.Canvas(self._sim_card, bg=BG2, height=self.CELL+16, highlightthickness=0)
        ref_xscroll = ttk.Scrollbar(self._sim_card, orient="horizontal", command=self.ref_canvas.xview)
        self.ref_canvas.configure(xscrollcommand=ref_xscroll.set)
        self.ref_canvas.pack(fill="x", padx=10, pady=(8, 0))
        ref_xscroll.pack(fill="x", padx=10, pady=(0, 6))
        tk.Frame(self._sim_card, bg=BORDER, height=1).pack(fill="x")

        # Frames Row
        fr_hdr = tk.Frame(self._sim_card, bg=BG3)
        fr_hdr.pack(fill="x")
        tk.Frame(fr_hdr, bg=MAGENTA, width=3).pack(side="left", fill="y")
        tk.Label(fr_hdr, text="FRAMES AT EACH STEP", bg=BG3, fg=TEXT, font=("Segoe UI", 8, "bold"), pady=8, padx=11).pack(anchor="w", side="left")
        
        self.frame_canvas = tk.Canvas(self._sim_card, bg=BG2, highlightthickness=0)
        fr_xscroll = ttk.Scrollbar(self._sim_card, orient="horizontal", command=self.frame_canvas.xview)
        self.frame_canvas.configure(xscrollcommand=fr_xscroll.set)
        self.frame_canvas.pack(fill="x", padx=10, pady=(8, 0))
        fr_xscroll.pack(fill="x", padx=10, pady=(0, 6))

        # Color Legend
        leg_frame = tk.Frame(self._sim_card, bg=BG2)
        leg_frame.pack(fill="x", padx=14, pady=(0, 15))
        
        for color, lbl in [(CYAN, "Hit"), (FAULT_COLOR, "Fault"), (MAGENTA, "Load"), (ORANGE, "Evict")]:
            block = tk.Frame(leg_frame, bg=BG2)
            block.pack(side="left", padx=(0, 20))
            dot = tk.Frame(block, bg=color, width=10, height=10)
            dot.pack(side="left")
            dot.pack_propagate(False)
            tk.Label(block, text=lbl, bg=BG2, fg=TEXT2, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(6, 0))

        tk.Frame(self._sim_card, bg=BORDER, height=1).pack(fill="x")

        # Tally Row (LFU/MFU)
        self._tally_wrapper = tk.Frame(self._sim_card, bg=BG2)
        self._tally_wrapper.pack(fill="x")
        tal_hdr = tk.Frame(self._tally_wrapper, bg=BG3)
        tal_hdr.pack(fill="x")
        tk.Frame(tal_hdr, bg=MAGENTA, width=3).pack(side="left", fill="y")
        self.tally_label_var = tk.StringVar(value="REFERENCE COUNTS")
        tk.Label(tal_hdr, textvariable=self.tally_label_var, bg=BG3, fg=TEXT, font=("Segoe UI", 8, "bold"), pady=8, padx=11).pack(anchor="w", side="left")
        
        self.tally_canvas = tk.Canvas(self._tally_wrapper, bg=BG2, height=90, highlightthickness=0)
        tal_xscroll = ttk.Scrollbar(self._tally_wrapper, orient="horizontal", command=self.tally_canvas.xview)
        self.tally_canvas.configure(xscrollcommand=tal_xscroll.set)
        self.tally_canvas.pack(fill="x", padx=10, pady=(8, 0))
        tal_xscroll.pack(fill="x", padx=10, pady=(0, 6))

        # ── Bottom Control Dock ──
        bot_bar = tk.Frame(main_content, bg=BG, height=80)
        bot_bar.pack(fill="x", padx=20, pady=(10, 20))
        bot_bar.pack_propagate(False)

        bot_bar.columnconfigure(0, weight=1)
        bot_bar.columnconfigure(1, weight=1)
        bot_bar.columnconfigure(2, weight=1)

        left_dock = tk.Frame(bot_bar, bg=BG)
        left_dock.grid(row=0, column=0, sticky="w", pady=15)
        self.step_label = tk.Label(left_dock, text="Step 0 / 0", bg=BG, fg=TEXT2, font=("Segoe UI", 11, "bold"))
        self.step_label.pack(side="left", padx=10)

        center_dock = tk.Frame(bot_bar, bg=BG)
        center_dock.grid(row=0, column=1, pady=15)

        btn_kw = dict(bg=BG3, fg=TEXT, font=("Segoe UI", 12), relief="flat", width=4, pady=6, cursor="hand2", activebackground=BORDER2, activeforeground=TEXT, highlightthickness=1, highlightbackground=BORDER)
        
        self.btn_prev = tk.Button(center_dock, text="⏮", command=self._prev, **btn_kw)
        self.btn_prev.pack(side="left", padx=4)
        self._bind_hover(self.btn_prev, BG3, BORDER2)
        
        self.play_btn = tk.Button(center_dock, text="⏵", command=self._toggle_play, bg=MAGENTA, fg=BG, font=("Segoe UI", 12, "bold"), relief="flat", width=6, pady=6, cursor="hand2", activebackground="#1A6BBF", activeforeground=MAGENTA, highlightthickness=0)
        self.play_btn.pack(side="left", padx=4)
        self._bind_hover(self.play_btn, MAGENTA, MAGENTA_H, BG, BG)
        
        self.btn_next = tk.Button(center_dock, text="⏭", command=self._next, **btn_kw)
        self.btn_next.pack(side="left", padx=4)
        self._bind_hover(self.btn_next, BG3, BORDER2)

        right_dock = tk.Frame(bot_bar, bg=BG)
        right_dock.grid(row=0, column=2, sticky="e", pady=15)
        self.btn_dock_reset = tk.Button(right_dock, text="↺", command=self._compute_and_reset, **btn_kw)
        self.btn_dock_reset.pack(side="right", padx=10)
        self._bind_hover(self.btn_dock_reset, BG3, BORDER2)

    def _on_card_configure(self, event):
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._scroll_canvas.itemconfig(self._card_win, width=event.width)

    def _style_tabs(self):
        for key, btn in self.tab_btns.items():
            if key == self.algo:
                btn.configure(bg=MAGENTA, fg=BG) 
                self._bind_hover(btn, MAGENTA, MAGENTA_H, BG, BG)
            else:
                btn.configure(bg=BG, fg=TEXT2)
                self._bind_hover(btn, BG, BG3, TEXT2, TEXT)

    def _on_preset_selected(self, event=None):
        self.custom_var.set("")          
        self._compute_and_reset()

    def _use_custom(self):
        raw = self.custom_var.get().strip()
        if not raw: return
        try:
            parsed = [int(x.strip()) for x in raw.replace(" ", ",").split(",") if x.strip()]
            if not parsed: raise ValueError
        except ValueError:
            messagebox.showerror("Invalid input", "Enter comma-separated integers, e.g.  1, 2, 3, 4, 1, 2")
            return
        self._stop_play()
        self.refs = parsed
        self.ref_var.set("Custom")      
        if "Custom" not in self.ref_cb["values"]: self.ref_cb["values"] = list(REF_STRINGS.keys()) + ["Custom"]
        self.steps = compute(self.algo, self.refs, self.frames_count)
        self.cur = -1
        self.desc_var.set(DESCS[self.algo])
        self._render()

    def _set_algo(self, algo):
        self.algo = algo
        self._style_tabs()
        self.desc_var.set(DESCS[algo])
        self._compute_and_reset()

    def _compute_and_reset(self):
        self._stop_play()
        key = self.ref_var.get()
        if key != "Custom": self.refs = REF_STRINGS.get(key, REF_STRINGS["Classic (7,0,1,2,0,3...)"])
        try: fc = int(self.frame_var.get())
        except Exception: fc = 3
        self.frames_count = max(1, min(9, fc))
        self.steps = compute(self.algo, self.refs, self.frames_count)
        self.cur = -1
        self.desc_var.set(DESCS[self.algo])
        self._render()

    def _render(self):
        is_counting = self.algo in ("lfu", "mfu")
        if is_counting: self._tally_wrapper.pack(fill="x")
        else: self._tally_wrapper.pack_forget()

        self._draw_ref_cells()
        self._draw_frame_grid()
        if is_counting and self.cur >= 0: self._draw_tally()
        self._update_info()
        self._update_stats()

    # ── Canvas drawing ─────────────────────────────────
    def _draw_ref_cells(self):
        c = self.ref_canvas; c.delete("all")
        CELL = self.CELL; GAP = self.GAP; pad = 4
        
        for i, r in enumerate(self.refs):
            x = pad + i * (CELL + GAP); y = pad + 4
            
            if i == self.cur:
                base_bg = BG3; text_fg = TEXT; accent = CYAN if self.steps[self.cur]["hit"] else FAULT_COLOR
                w = 2
            elif self.cur >= 0 and i < self.cur:
                base_bg = BG; text_fg = TEXT2; accent = CYAN if self.steps[i]["hit"] else FAULT_COLOR
                w = 1
            else:
                base_bg = BG; text_fg = TEXT3; accent = BORDER
                w = 1
            
            self._create_round_rect(c, x, y, x+CELL, y+CELL, radius=6, fill=base_bg, outline=accent, width=w)
            c.create_text(x+CELL/2, y+CELL/2, text=str(r), fill=text_fg, font=("Segoe UI", 11, "bold"), justify="center")
            
        total_w = pad + len(self.refs)*(CELL+GAP) + pad
        c.configure(scrollregion=(0, 0, total_w, CELL+16), height=CELL+16)

    def _draw_frame_grid(self):
        c = self.frame_canvas; c.delete("all")
        CELL = self.CELL; GAP = self.GAP; HDR = 18
        n = self.frames_count; col_w = CELL+GAP; pad = 4
        total_h = HDR + n*(CELL+GAP) + pad + 8

        if self.cur < 0:
            x = pad
            c.create_text(x+CELL//2, HDR//2, text="—", fill=TEXT3, font=("Segoe UI", 8, "bold"))
            for f in range(n):
                y = HDR + f*(CELL+GAP)
                self._create_round_rect(c, x, y, x+CELL, y+CELL, radius=6, fill=BG, outline=BORDER, width=1)
                c.create_text(x+CELL/2, y+CELL/2, text="—", fill=TEXT3, font=("Segoe UI", 10), justify="center")
            c.configure(scrollregion=(0, 0, pad+CELL+pad, total_h), height=total_h)
            return

        for step in range(self.cur + 1):
            s = self.steps[step]; x = pad + step*col_w
            
            step_fg = CYAN if s["hit"] else FAULT_COLOR
            c.create_text(x+CELL//2, HDR//2, text=str(step+1), fill=step_fg, font=("Segoe UI", 8, "bold"))
            
            is_hit_col = (step == self.cur and s["hit"])

            for f in range(n):
                y = HDR + f*(CELL+GAP)
                val = s["mem"][f] if f < len(s["mem"]) else None
                w = 1
                
                if val is None:
                    base_bg = BG; text_fg = TEXT3; accent = BORDER; lbl = ""
                elif is_hit_col:
                    base_bg = BG3; text_fg = CYAN; accent = CYAN; lbl = str(val); w=2
                elif step == self.cur and not s["hit"] and val == s["page"]:
                    base_bg = BG3; text_fg = TEXT; accent = MAGENTA; lbl = str(val); w=2
                elif step == self.cur and val == s.get("victim") and s["victim"] is not None:
                    base_bg = BG; text_fg = ORANGE; accent = ORANGE; lbl = str(val); w=2
                else:
                    base_bg = BG; text_fg = TEXT; accent = BORDER2; lbl = str(val)

                self._create_round_rect(c, x, y, x+CELL, y+CELL, radius=6, fill=base_bg, outline=accent, width=w)
                if lbl != "":
                    c.create_text(x+CELL/2, y+CELL/2, text=lbl, fill=text_fg, font=("Segoe UI", 11, "bold"), justify="center")

        total_w = pad + (self.cur+1)*col_w + pad
        c.configure(scrollregion=(0, 0, total_w, total_h), height=total_h)

    def _draw_tally(self):
        c = self.tally_canvas
        c.delete("all")
        s = self.steps[self.cur]
        counts = s.get("counts") or {}
        if not counts: return

        lbl_strat = "(Lowest = Evict Target)" if self.algo == "lfu" else "(Highest = Evict Target)"
        self.tally_label_var.set(f"REFERENCE COUNTS {lbl_strat}")

        CARD_W = 80
        CARD_H = 66
        GAP = 12
        pad = 4

        for i, pg in enumerate(sorted(counts.keys())):
            cnt = counts[pg]
            in_mem    = pg in s["mem"]
            is_victim = pg == s.get("victim") and not s["hit"]
            is_cur    = pg == s["page"]

            x = pad + i * (CARD_W + GAP)
            y = pad + 4

            if is_victim:
                bg = BG; accent = ORANGE; lbl_stat = "EVICT"; w=2
            elif is_cur and not is_victim:
                bg = BG3; accent = CYAN; lbl_stat = "CURRENT"; w=2
            elif in_mem:
                bg = BG; accent = MAGENTA; lbl_stat = "IN MEM"; w=1
            else:
                bg = BG; accent = BORDER; lbl_stat = "IDLE"; w=1

            self._create_round_rect(c, x, y, x+CARD_W, y+CARD_H, radius=6, fill=bg, outline=accent, width=w)
            c.create_rectangle(x, y, x+CARD_W, y+4, fill=accent if in_mem else BORDER2, outline="")
            c.create_text(x+CARD_W/2, y+30, text=str(cnt), fill=TEXT, font=("Segoe UI", 22, "bold"), justify="center")
            c.create_text(x+CARD_W/2, y+52, text=f"PG {pg} • {lbl_stat}", fill=accent if in_mem else TEXT3, font=("Segoe UI", 7, "bold"), justify="center")

        total_w = pad + len(counts)*(CARD_W+GAP) + pad
        c.configure(scrollregion=(0, 0, total_w, CARD_H+16), height=CARD_H+16)

    def _update_info(self):
        if self.cur < 0: 
            self.status_pill.config(text="WAIT", bg=BG3, fg=TEXT2)
            self.status_frame.config(highlightbackground=BORDER)
            self.info_var.set("SYSTEM IDLE  —  Awaiting trace execution.")
            return
            
        s = self.steps[self.cur]
        if s["hit"]:
            self.status_pill.config(text="HIT", bg=CYAN, fg=BG)
            self.status_frame.config(highlightbackground=CYAN)
            msg = f"Page {s['page']} is already in memory."
        elif s["victim"] is not None:
            self.status_pill.config(text="FAULT", bg=FAULT_COLOR, fg=BG)
            self.status_frame.config(highlightbackground=FAULT_COLOR)
            msg = f"Page {s['page']} requested. Evicted Page {s['victim']}."
        else:
            self.status_pill.config(text="FAULT", bg=FAULT_COLOR, fg=BG)
            self.status_frame.config(highlightbackground=FAULT_COLOR)
            msg = f"Page {s['page']} loaded into an empty frame."
            
        if self.algo == "second" and s.get("bits"): msg += f" (Bits: [{', '.join(str(b) for b in s['bits'])}])"
        self.info_var.set(msg)

    def _update_stats(self):
        shown  = self.steps[:max(0, self.cur+1)]
        faults = sum(1 for st in shown if not st["hit"])
        hits   = sum(1 for st in shown if     st["hit"])
        total  = len(shown)
        self.stat_faults.set(str(faults))
        self.stat_hits.set(str(hits))
        self.stat_total.set(str(total))
        self.stat_rate.set(f"{round(faults/total*100)}%" if total else "0%")
        self.step_label.configure(text=f"Step {max(0, self.cur+1)} / {len(self.steps)}")

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
        self.play_btn.configure(text="⏸", bg=FAULT_COLOR, fg=BG)
        self._bind_hover(self.play_btn, FAULT_COLOR, FAULT_COLOR_H, BG, BG)
        self._tick()

    def _stop_play(self):
        self._playing = False
        if self._timer: self.after_cancel(self._timer); self._timer = None
        self.play_btn.configure(text="⏵", bg=MAGENTA, fg=BG)
        self._bind_hover(self.play_btn, MAGENTA, MAGENTA_H, BG, BG)

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
    root.minsize(1050, 700)
    root.configure(bg=BG)
    app = PageReplacementApp(root)
    app.pack(fill="both", expand=True)
    root.mainloop()
