import tkinter as tk
import copy

# ── palette ──────────────────────────────────────────────────────────────────
PC     = ['#5B8DF5','#F5A023','#22C55E','#F05070','#A855F7','#EAB308','#06B6D4','#F97316']
BG     = '#0f0f0f'
BG2    = '#181818'
BORD   = '#2a2a2a'
TXT    = '#e0e0e0'
TXT2   = '#888888'
TXT3   = '#444444'
ST_COL = {'waiting':'#555555','ready':'#F5A023','running':'#22C55E','finished':'#5B8DF5'}
CW, CH = 26, 22

ALGOS = [
    ('FCFS',           'FCFS',      False),
    ('SJF',            'SJF',       False),
    ('SJF Preemptive', 'SRTF',      True),
    ('Round Robin',    'RR',        True),
    ('Priority',       'Priority',  False),
    ('Priority Pre.',  'PriorityP', True),
]
ALGO_KEYS   = [a[1] for a in ALGOS]
ALGO_LABELS = {a[1]: a[0] for a in ALGOS}

INIT_PROCS = [
    {'id':'P1','at':0,'bt':5,'pr':3},
    {'id':'P2','at':1,'bt':3,'pr':1},
    {'id':'P3','at':2,'bt':8,'pr':4},
    {'id':'P4','at':3,'bt':2,'pr':2},
]

def pcol(procs, pid):
    for i, p in enumerate(procs):
        if p['id'] == pid:
            return PC[i % len(PC)]
    return '#888'

def blend(hex_col, alpha):
    r,g,b    = int(hex_col[1:3],16), int(hex_col[3:5],16), int(hex_col[5:7],16)
    br,bg,bb = int(BG[1:3],16),      int(BG[3:5],16),      int(BG[5:7],16)
    return '#{:02x}{:02x}{:02x}'.format(
        int(r*alpha + br*(1-alpha)),
        int(g*alpha + bg*(1-alpha)),
        int(b*alpha + bb*(1-alpha)))


# ─────────────────────────────────────────────────────────────────────────────
class App(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG)

        self.procs = copy.deepcopy(INIT_PROCS)
        self.algo  = 'FCFS'
        self.tq    = 2
        self.sim   = None

        # live-update widget references (populated in _build_sim_ui)
        self._step_btn      = None
        self._step_lbl      = None
        self._card_clock    = None
        self._card_running  = None
        self._queue_row     = None
        self._card_tq_frame = None
        self._card_tq_val   = None
        self._row_widgets   = {}   # pid -> {'rem': Label, 'state': Label}
        self._gantt_canvas  = None
        self._gantt_hsb     = None
        self._gantt_outer   = None
        self._stats_outer   = None

        # scrollable container
        self._vsb = tk.Scrollbar(self, orient='vertical')
        self._vsb.pack(side='right', fill='y')
        self._cv  = tk.Canvas(self, bg=BG, yscrollcommand=self._vsb.set,
                              highlightthickness=0)
        self._cv.pack(side='left', fill='both', expand=True)
        self._vsb.config(command=self._cv.yview)

        self.f    = tk.Frame(self._cv, bg=BG)
        self._fid = self._cv.create_window((0,0), window=self.f, anchor='nw')

        self.f.bind('<Configure>',   self._on_frame_cfg)
        self._cv.bind('<Configure>', self._on_cv_cfg)
        self.bind_all('<MouseWheel>', lambda e:
            self._cv.yview_scroll(int(-1*(e.delta/120)), 'units'))
        self.bind_all('<Button-4>', lambda e: self._cv.yview_scroll(-1,'units'))
        self.bind_all('<Button-5>', lambda e: self._cv.yview_scroll( 1,'units'))
        self.bind('<space>',  self._on_space)
        self.bind('<Return>', self._on_space)

        self._render()

    # ── scrollable frame plumbing ─────────────────────────────────────────────
    def _on_frame_cfg(self, e):
        self._cv.configure(scrollregion=self._cv.bbox('all'))

    def _on_cv_cfg(self, e):
        self._cv.itemconfig(self._fid, width=e.width)

    # ─────────────────────────────────────────────────────────────────────────
    # FULL RENDER  –  called only on: app start, reset, algo change, proc edits
    # ─────────────────────────────────────────────────────────────────────────
    def _render(self):
        # clear live-widget refs so stale handles aren't used
        self._step_btn = self._step_lbl = None
        self._card_clock = self._card_running = None
        self._queue_row  = None
        self._card_tq_frame = self._card_tq_val = None
        self._row_widgets   = {}
        self._gantt_canvas  = self._gantt_hsb = self._gantt_outer = None
        self._stats_outer   = None

        for w in self.f.winfo_children():
            w.destroy()
        P = 20

        # ── header ────────────────────────────────────────────────────────────
        hf = tk.Frame(self.f, bg=BG)
        hf.pack(fill='x', padx=P, pady=(16,10))
        tk.Label(hf, text='CPU SCHEDULING SIMULATOR', bg=BG, fg=TXT3,
                 font=('Courier New',9)).pack(side='left')
        if self.sim:
            tk.Label(hf, text=f' {ALGO_LABELS[self.algo]} ', bg=BG, fg='#5B8DF5',
                     font=('Courier New',9), bd=1, relief='solid').pack(side='left', padx=8)

        # ── algo buttons ──────────────────────────────────────────────────────
        for row_keys in [['FCFS','SJF','SRTF','RR'], ['Priority','PriorityP']]:
            af = tk.Frame(self.f, bg=BG)
            af.pack(fill='x', padx=P, pady=(0,4))
            for key in row_keys:
                active = (key == self.algo)
                is_pre = key in ('SRTF','RR','PriorityP')
                abg = '#5B8DF5' if (active and is_pre) else (TXT if active else BG)
                afg = BG if active else TXT2
                tk.Button(af, text=ALGO_LABELS[key], font=('Courier New',9),
                    bg=abg, fg=afg, relief='solid', bd=1,
                    highlightbackground=BORD, padx=8, pady=3,
                    cursor='hand2' if not self.sim else 'arrow',
                    command=(lambda _k=key: self._set_algo(_k)) if not self.sim else None
                ).pack(side='left', padx=(0,4))
            if 'RR' in row_keys and self.algo == 'RR':
                tk.Label(af, text='TQ =', bg=BG, fg=TXT2,
                         font=('Courier New',9)).pack(side='left', padx=(8,2))
                sv = tk.StringVar(value=str(self.tq))
                sp = tk.Spinbox(af, from_=1, to=20, width=4, textvariable=sv,
                                font=('Courier New',10), bg=BG2, fg=TXT,
                                insertbackground=TXT, relief='flat',
                                state='normal' if not self.sim else 'disabled')
                sp.bind('<FocusOut>',  lambda e, v=sv: self._set_tq(v.get()))
                sp.bind('<<Modified>>',lambda e, v=sv: self._set_tq(v.get()))
                sp.pack(side='left')

        # legend
        lf = tk.Frame(self.f, bg=BG)
        lf.pack(fill='x', padx=P, pady=(0,8))
        tk.Label(lf, text='● Non-preemptive', bg=BG, fg=TXT3,
                 font=('Courier New',8)).pack(side='left', padx=(0,12))
        tk.Label(lf, text='● Preemptive', bg=BG, fg='#5B8DF5',
                 font=('Courier New',8)).pack(side='left')

        # ── process table ─────────────────────────────────────────────────────
        self._build_table(P)

        # ── control bar ───────────────────────────────────────────────────────
        bf = tk.Frame(self.f, bg=BG)
        bf.pack(fill='x', padx=P, pady=(0,14))
        if not self.sim:
            tk.Button(bf, text='▶  START', font=('Courier New',11,'bold'),
                bg=TXT, fg=BG, relief='flat', padx=18, pady=8,
                cursor='hand2', command=self._init_sim).pack(side='left')
        else:
            done = self.sim['done']
            self._step_btn = tk.Button(bf,
                text='■  DONE' if done else f'⏭  STEP   t = {self.sim["t"]} →',
                font=('Courier New',11,'bold'),
                bg=BG2 if done else TXT, fg=TXT3 if done else BG,
                relief='flat', padx=22, pady=8,
                state='disabled' if done else 'normal',
                cursor='arrow' if done else 'hand2',
                command=self._step)
            self._step_btn.pack(side='left')
            tk.Button(bf, text='↺  RESET', font=('Courier New',9),
                bg=BG, fg=TXT2, relief='solid', bd=1,
                highlightbackground=BORD, padx=12, pady=8,
                cursor='hand2', command=self._reset).pack(side='left', padx=8)
            lbl = '✓  All processes finished' if done else '— or press Space'
            self._step_lbl = tk.Label(bf, text=lbl, bg=BG,
                fg='#22C55E' if done else TXT3,
                font=('Courier New', 10 if done else 9))
            self._step_lbl.pack(side='left', padx=4)

        # ── sim-only sections (built once, updated in-place) ──────────────────
        if self.sim:
            self._build_cards(P)
            self._build_gantt_shell(P)
            if self.sim['done']:
                self._build_stats(P)
            # draw initial state
            self._redraw_gantt()

        tk.Frame(self.f, bg=BG, height=24).pack()

    # ── process table ─────────────────────────────────────────────────────────
    def _build_table(self, P):
        running = bool(self.sim)
        wrap = tk.Frame(self.f, bg=BORD, padx=1, pady=1)
        wrap.pack(fill='x', padx=P, pady=(0,10))
        cont = tk.Frame(wrap, bg=BG)
        cont.pack(fill='x')

        cols = ['PID','ARRIVAL','BURST','PRIORITY'] + (['REM.','STATE'] if running else [])
        cw   = [7,9,7,9,6,11]

        hrow = tk.Frame(cont, bg=BG2)
        hrow.pack(fill='x')
        for ci,h in enumerate(cols):
            tk.Label(hrow, text=h, bg=BG2, fg=TXT3,
                     font=('Courier New',8), width=cw[ci],
                     anchor='w', padx=8, pady=5).grid(row=0, column=ci, sticky='w')

        for i, p in enumerate(self.procs):
            col = pcol(self.procs, p['id'])
            ps  = self.sim['ps'][p['id']] if self.sim else None
            tk.Frame(cont, bg=BORD, height=1).pack(fill='x')
            row = tk.Frame(cont, bg=BG)
            row.pack(fill='x')

            df = tk.Frame(row, bg=BG)
            df.pack(side='left', padx=(8,4), pady=5)
            dot = tk.Canvas(df, width=9, height=9, bg=BG, highlightthickness=0)
            dot.pack(side='left', padx=(0,5))
            dot.create_rectangle(1,1,8,8, fill=col, outline=col)
            if running:
                tk.Label(df, text=p['id'], bg=BG, fg=TXT,
                         font=('Courier New',10), width=5, anchor='w').pack(side='left')
            else:
                e = tk.Entry(df, width=5, bg=BG, fg=TXT, insertbackground=TXT,
                             relief='flat', font=('Courier New',10))
                e.insert(0, p['id'])
                e.bind('<FocusOut>', lambda ev, idx=i: self._upd_id(idx, ev.widget.get()))
                e.pack(side='left')

            for fld in ['at','bt','pr']:
                cf = tk.Frame(row, bg=BG)
                cf.pack(side='left', padx=6)
                if running:
                    tk.Label(cf, text=str(p[fld]), bg=BG, fg=TXT,
                             font=('Courier New',10), width=6, anchor='w').pack()
                else:
                    e2 = tk.Entry(cf, width=5, bg=BG, fg=TXT, insertbackground=TXT,
                                  relief='flat', font=('Courier New',10))
                    e2.insert(0, str(p[fld]))
                    e2.bind('<FocusOut>', lambda ev, idx=i, f=fld:
                            self._upd_num(idx, f, ev.widget.get()))
                    e2.pack()

            if ps:
                rem_col = TXT3 if ps['rem'] == 0 else TXT
                fw = 'bold' if ps['state'] == 'running' else 'normal'
                rem_lbl = tk.Label(row, text=str(ps['rem']), bg=BG, fg=rem_col,
                                   font=('Courier New',10,fw), width=5, anchor='w')
                rem_lbl.pack(side='left', padx=6)
                sc = ST_COL[ps['state']]
                st_lbl = tk.Label(row,
                    text=ps['state'].upper() + (' ▶' if ps['state'] == 'running' else ''),
                    bg=blend(sc,0.20), fg=sc,
                    font=('Courier New',8), padx=6, pady=2)
                st_lbl.pack(side='left', padx=4)
                self._row_widgets[p['id']] = {'rem': rem_lbl, 'state': st_lbl}

            if not running:
                tk.Button(row, text='×', bg=BG, fg=TXT3, relief='flat',
                          font=('Courier New',14), cursor='hand2',
                          command=lambda idx=i: self._del_proc(idx)).pack(side='right', padx=6)

        if not running:
            tk.Frame(cont, bg=BORD, height=1).pack(fill='x')
            tk.Button(cont, text='+ ADD PROCESS', bg=BG, fg=TXT3,
                      font=('Courier New',9), relief='flat', pady=7,
                      cursor='hand2', command=self._add_proc).pack(fill='x')

    # ── status cards (built once) ─────────────────────────────────────────────
    def _build_cards(self, P):
        cf = tk.Frame(self.f, bg=BG)
        cf.pack(fill='x', padx=P, pady=(0,12))

        def card(label, value, fg=TXT, fs=20):
            c = tk.Frame(cf, bg=BG2, highlightbackground=BORD, highlightthickness=1)
            c.pack(side='left', fill='both', expand=True, padx=(0,8))
            tk.Label(c, text=label, bg=BG2, fg=TXT3,
                     font=('Courier New',8), anchor='w', padx=10).pack(fill='x', pady=(6,0))
            v = tk.Label(c, text=str(value), bg=BG2, fg=fg,
                         font=('Courier New',fs,'bold'), anchor='w', padx=10)
            v.pack(fill='x', pady=(2,8))
            return v

        self._card_clock   = card('CLOCK',   self.sim['t'])
        cur = self.sim['cur']
        self._card_running = card('RUNNING', cur or 'IDLE',
                                  fg=pcol(self.procs,cur) if cur else TXT3,
                                  fs=18 if cur else 12)

        # ready queue card
        qc = tk.Frame(cf, bg=BG2, highlightbackground=BORD, highlightthickness=1)
        qc.pack(side='left', fill='both', expand=True, padx=(0,8))
        tk.Label(qc, text='READY QUEUE', bg=BG2, fg=TXT3,
                 font=('Courier New',8), anchor='w', padx=10).pack(fill='x', pady=(6,0))
        self._queue_row = tk.Frame(qc, bg=BG2)
        self._queue_row.pack(fill='x', padx=10, pady=(2,8))
        self._redraw_queue()

        # TQ card (only for RR)
        if self.algo == 'RR':
            self._card_tq_frame = tk.Frame(cf, bg=BG2,
                                           highlightbackground=BORD, highlightthickness=1)
            self._card_tq_frame.pack(side='left', fill='both', expand=True, padx=(0,8))
            tk.Label(self._card_tq_frame, text='TQ LEFT', bg=BG2, fg=TXT3,
                     font=('Courier New',8), anchor='w', padx=10
                     ).pack(fill='x', pady=(6,0))
            self._card_tq_val = tk.Label(self._card_tq_frame,
                text=str(self.sim['tqLeft']), bg=BG2, fg='#F5A023',
                font=('Courier New',20,'bold'), anchor='w', padx=10)
            self._card_tq_val.pack(fill='x', pady=(2,8))

    def _redraw_queue(self):
        """Repopulate only the queue row labels — no widget destruction elsewhere."""
        for w in self._queue_row.winfo_children():
            w.destroy()
        q = self.sim['q']
        if not q:
            tk.Label(self._queue_row, text='[ empty ]', bg=BG2, fg=TXT3,
                     font=('Courier New',11)).pack(side='left')
        else:
            for j, pid in enumerate(q):
                tk.Label(self._queue_row, text=pid, bg=BG2,
                         fg=pcol(self.procs,pid),
                         font=('Courier New',11,'bold')).pack(side='left')
                if j < len(q)-1:
                    tk.Label(self._queue_row, text=' → ', bg=BG2, fg=TXT3,
                             font=('Courier New',11)).pack(side='left')

    # ── gantt shell (built once, canvas redrawn each step) ────────────────────
    def _build_gantt_shell(self, P):
        n     = len(self.procs)
        ROW_H = 30
        TOP   = 18
        cv_h  = TOP + n*ROW_H + 8

        outer = tk.Frame(self.f, bg=BG2, highlightbackground=BORD, highlightthickness=1)
        outer.pack(fill='x', padx=P, pady=(0,10))
        self._gantt_outer = outer

        tk.Label(outer, text='GANTT CHART', bg=BG2, fg=TXT3,
                 font=('Courier New',8), anchor='w', padx=14, pady=8).pack(fill='x')

        holder = tk.Frame(outer, bg=BG2)
        holder.pack(fill='x', padx=14, pady=(0,12))

        self._gantt_hsb = tk.Scrollbar(holder, orient='horizontal')
        self._gantt_hsb.pack(side='bottom', fill='x')

        self._gantt_canvas = tk.Canvas(holder, bg=BG, height=cv_h,
                                       highlightthickness=0,
                                       xscrollcommand=self._gantt_hsb.set)
        self._gantt_canvas.pack(side='top', fill='x', expand=True)
        self._gantt_hsb.config(command=self._gantt_canvas.xview)
        self._gantt_P = P   # store for redraw

    def _redraw_gantt(self):
        """Wipe and redraw only the Gantt canvas contents — zero widget churn."""
        if not self._gantt_canvas:
            return
        gc   = self._gantt_canvas
        log  = self.sim['log']
        maxT = len(log)
        if maxT == 0:
            return

        X0    = 48
        ROW_H = 30
        TOP   = 18
        n     = len(self.procs)
        cv_w  = X0 + maxT*CW + 20

        gc.delete('all')
        gc.configure(scrollregion=(0, 0, cv_w, TOP + n*ROW_H + 8))

        # finish times
        fin = {}
        for p in self.procs:
            slots = [e['t'] for e in log if e['pid'] == p['id']]
            fin[p['id']] = (slots[-1]+1) if slots else float('inf')

        # time labels
        for i in range(maxT+1):
            gc.create_text(X0 + i*CW, 2, text=str(i),
                           fill=TXT3, font=('Courier New',7), anchor='n')

        for ri, p in enumerate(self.procs):
            col = pcol(self.procs, p['id'])
            y0  = TOP + ri*ROW_H
            yc  = y0 + CH//2

            gc.create_text(2, yc, text=p['id'],
                           fill=TXT2, font=('Courier New',9,'bold'), anchor='w')

            for t in range(maxT):
                entry   = log[t]
                is_run  = entry['pid'] == p['id']
                arrived = t >= p['at']
                is_done = t >= fin[p['id']]
                x0 = X0 + t*CW
                x1 = x0 + CW

                if is_run:
                    gc.create_rectangle(x0, y0, x1, y0+CH, fill=col, outline=col)
                    gc.create_text(x0+CW//2, yc, text=p['id'],
                                   fill='white', font=('Courier New',7,'bold'))
                elif arrived and not is_done:
                    gc.create_rectangle(x0, y0, x1, y0+CH,
                                        fill=blend(col,0.14), outline=blend(col,0.32))
                else:
                    gc.create_rectangle(x0, y0, x1, y0+CH, fill=BG, outline=BORD)

        gc.xview_moveto(1.0)
        self._cv.configure(scrollregion=self._cv.bbox('all'))

    # ── statistics (built once at sim end, shown via pack/unpack) ────────────
    def _build_stats(self, P):
        if self._stats_outer and self._stats_outer.winfo_exists():
            return  # already built
        log   = self.sim['log']
        stats = []
        for p in self.procs:
            runs  = [i for i,l in enumerate(log) if l['pid'] == p['id']]
            first = runs[0]  if runs else -1
            comp  = runs[-1]+1 if runs else 0
            tat   = comp - p['at']
            wait  = tat  - p['bt']
            resp  = first - p['at'] if first >= 0 else 0
            stats.append({'id':p['id'],'comp':comp,'tat':tat,'wait':wait,'resp':resp})

        outer = tk.Frame(self.f, bg=BG2, highlightbackground=BORD, highlightthickness=1)
        outer.pack(fill='x', padx=P, pady=(0,10))
        self._stats_outer = outer

        tk.Label(outer, text='STATISTICS', bg=BG2, fg=TXT3,
                 font=('Courier New',8), anchor='w', padx=14, pady=8).pack(fill='x')

        tf = tk.Frame(outer, bg=BG)
        tf.pack(fill='x')
        for c in range(5): tf.grid_columnconfigure(c, weight=1)

        for ci, h in enumerate(['PID','COMPLETION','TURNAROUND','WAITING','RESPONSE']):
            tk.Label(tf, text=h, bg=BG2, fg=TXT3, font=('Courier New',8),
                     anchor='w', padx=10, pady=5).grid(row=0, column=ci, sticky='ew')

        for ri, s in enumerate(stats):
            col = pcol(self.procs, s['id'])
            tk.Frame(tf, bg=BORD, height=1).grid(
                row=ri*2+1, column=0, columnspan=5, sticky='ew')
            row = ri*2+2
            pf = tk.Frame(tf, bg=BG)
            pf.grid(row=row, column=0, sticky='w', padx=10, pady=6)
            dot = tk.Canvas(pf, width=9, height=9, bg=BG, highlightthickness=0)
            dot.pack(side='left', padx=(0,5))
            dot.create_rectangle(1,1,8,8, fill=col, outline=col)
            tk.Label(pf, text=s['id'], bg=BG, fg=TXT,
                     font=('Courier New',10)).pack(side='left')
            for ci, k in enumerate(['comp','tat','wait','resp']):
                tk.Label(tf, text=str(s[k]), bg=BG, fg=TXT,
                         font=('Courier New',10), anchor='w', padx=10
                         ).grid(row=row, column=ci+1, sticky='ew', pady=6)

        n = len(stats)
        tk.Frame(tf, bg=BORD, height=1).grid(
            row=n*2+1, column=0, columnspan=5, sticky='ew')
        tk.Label(tf, text='AVG', bg=BG2, fg=TXT3, font=('Courier New',8),
                 anchor='w', padx=10, pady=6).grid(row=n*2+2, column=0, sticky='ew')
        tk.Label(tf, text='', bg=BG2).grid(row=n*2+2, column=1, sticky='ew')
        for ci, k in enumerate(['tat','wait','resp']):
            avg = sum(s[k] for s in stats) / len(stats)
            tk.Label(tf, text=f'{avg:.2f}', bg=BG2, fg=TXT,
                     font=('Courier New',10,'bold'), anchor='w', padx=10, pady=6
                     ).grid(row=n*2+2, column=ci+2, sticky='ew')

    # ─────────────────────────────────────────────────────────────────────────
    # PARTIAL UPDATE  –  called every step; only touches live-update widgets
    # ─────────────────────────────────────────────────────────────────────────
    def _update_ui(self):
        s    = self.sim
        done = s['done']
        P    = 20

        # step button + label
        if self._step_btn:
            if done:
                self._step_btn.config(text='■  DONE', bg=BG2, fg=TXT3,
                                      state='disabled', cursor='arrow')
            else:
                self._step_btn.config(text=f'⏭  STEP   t = {s["t"]} →',
                                      bg=TXT, fg=BG, state='normal', cursor='hand2')
        if self._step_lbl:
            if done:
                self._step_lbl.config(text='✓  All processes finished',
                                      fg='#22C55E', font=('Courier New',10))
            else:
                self._step_lbl.config(text='— or press Space',
                                      fg=TXT3, font=('Courier New',9))

        # clock card
        if self._card_clock:
            self._card_clock.config(text=str(s['t']))

        # running card
        if self._card_running:
            cur = s['cur']
            self._card_running.config(
                text=cur or 'IDLE',
                fg=pcol(self.procs, cur) if cur else TXT3,
                font=('Courier New', 18 if cur else 12, 'bold'))

        # ready queue
        if self._queue_row:
            self._redraw_queue()

        # TQ card
        if self._card_tq_val and s['cur']:
            self._card_tq_val.config(text=str(s['tqLeft']))

        # process table rows
        for p in self.procs:
            ws = self._row_widgets.get(p['id'])
            if not ws:
                continue
            ps  = s['ps'][p['id']]
            sc  = ST_COL[ps['state']]
            fw  = 'bold' if ps['state'] == 'running' else 'normal'
            rc  = TXT3 if ps['rem'] == 0 else TXT
            ws['rem'].config(text=str(ps['rem']), fg=rc,
                             font=('Courier New',10,fw))
            ws['state'].config(
                text=ps['state'].upper() + (' ▶' if ps['state'] == 'running' else ''),
                bg=blend(sc, 0.20), fg=sc)

        # gantt canvas — fast pixel-level redraw, no widget creation
        self._redraw_gantt()

        # stats — build once when sim finishes, no rebuild after
        if done:
            self._build_stats(P)

        self._cv.configure(scrollregion=self._cv.bbox('all'))

    # ── simulation logic ──────────────────────────────────────────────────────
    def _init_sim(self):
        if not self.procs:
            return
        ps = {p['id']:{'rem':p['bt'],'state':'waiting'} for p in self.procs}
        self.sim = {'t':0,'ps':ps,'q':[],'cur':None,'tqLeft':self.tq,'log':[],'done':False}
        self._render()

    def _step(self):
        if not self.sim or self.sim['done']:
            return
        s  = self.sim
        ps = {k:dict(v) for k,v in s['ps'].items()}
        q, cur, tqLeft, t = list(s['q']), s['cur'], s['tqLeft'], s['t']
        log, algo = list(s['log']), self.algo

        for p in self.procs:
            if p['at'] == t and ps[p['id']]['state'] == 'waiting':
                ps[p['id']]['state'] = 'ready'
                q.append(p['id'])

        if algo == 'SRTF':
            q.sort(key=lambda pid: ps[pid]['rem'])
            if cur and q and ps[q[0]]['rem'] < ps[cur]['rem']:
                ps[cur]['state'] = 'ready'
                q.insert(0, cur)
                q.sort(key=lambda pid: ps[pid]['rem'])
                cur = None
        elif algo == 'PriorityP':
            q.sort(key=lambda pid: next(p['pr'] for p in self.procs if p['id']==pid))
            if cur and q:
                cur_pr   = next(p['pr'] for p in self.procs if p['id']==cur)
                best_pr  = next(p['pr'] for p in self.procs if p['id']==q[0])
                if best_pr < cur_pr:
                    ps[cur]['state'] = 'ready'
                    q.append(cur)
                    q.sort(key=lambda pid: next(p['pr'] for p in self.procs if p['id']==pid))
                    cur = None
        elif algo == 'SJF':
            q.sort(key=lambda pid: next(p['bt'] for p in self.procs if p['id']==pid))
        elif algo == 'Priority':
            q.sort(key=lambda pid: next(p['pr'] for p in self.procs if p['id']==pid))

        if algo == 'RR' and cur and tqLeft <= 0:
            if ps[cur]['state'] == 'running':
                ps[cur]['state'] = 'ready'
                q.append(cur)
            cur = None

        if not cur and q:
            cur = q.pop(0)
            ps[cur]['state'] = 'running'
            tqLeft = self.tq if algo == 'RR' else 9999

        if cur:
            log.append({'pid': cur, 't': t})
            ps[cur]['rem'] -= 1
            tqLeft -= 1
            if ps[cur]['rem'] <= 0:
                ps[cur]['state'] = 'finished'
                cur = None
                tqLeft = 0
        else:
            log.append({'pid': None, 't': t})

        done = all(ps[p['id']]['state'] == 'finished' for p in self.procs)
        self.sim = {'t':t+1,'ps':ps,'q':q,'cur':cur,'tqLeft':tqLeft,'log':log,'done':done}

        # ← partial update instead of full re-render
        self._update_ui()

    def _reset(self):
        self.sim = None
        self._render()

    def _add_proc(self):
        self.procs.append({'id':f'P{len(self.procs)+1}','at':0,'bt':1,'pr':1})
        self._render()

    def _del_proc(self, idx):
        self.procs.pop(idx)
        self._render()

    def _upd_id(self, idx, val):
        self.procs[idx]['id'] = val

    def _upd_num(self, idx, field, val):
        try:    self.procs[idx][field] = max(0, int(val))
        except: self.procs[idx][field] = 0

    def _set_algo(self, key):
        if self.sim: return
        self.algo = key
        self._render()

    def _set_tq(self, val):
        try: self.tq = max(1, int(val))
        except: pass

    def _on_space(self, e):
        if self.sim and not self.sim['done']:
            self._step()


if __name__ == '__main__':
    root = tk.Tk()
    root.title('CPU Scheduling Simulator')
    root.geometry('1020x680')
    root.minsize(800, 500)
    root.configure(bg=BG)
    app = App(root)
    app.pack(fill='both', expand=True)
    root.mainloop()