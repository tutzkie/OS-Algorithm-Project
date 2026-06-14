import tkinter as tk
from tkinter import ttk, font
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import math

# ─── Palette ───────────────────────────────────────────────────────────────────
BG         = "#ffffff"
BG2        = "#f5f5f5"
TEXT       = "#1a1a1a"
TEXT2      = "#666666"
BORDER     = "#d0d0d0"
INFO_BG    = "#e8f0fe"
INFO_TEXT  = "#1a56db"
INFO_BDR   = "#93bbe8"
ACCENT     = "#378ADD"

# ─── Algorithm logic (ported from JS) ──────────────────────────────────────────

def build_steps(head, queue, direction, disk, algo):
    result = []
    remaining = list(queue)
    pos = head

    if algo == "fcfs":
        for t in queue:
            result.append({"from": pos, "to": t, "note": f"Service track {t}"})
            pos = t

    elif algo == "sstf":
        while remaining:
            closest = min(remaining, key=lambda t: abs(t - pos))
            result.append({"from": pos, "to": closest,
                            "note": f"Closest: track {closest} (dist {abs(closest - pos)})"})
            pos = closest
            remaining.remove(closest)

    elif algo == "scan":
        sorted_q = sorted(remaining)
        go_up = (direction == "up")
        if not go_up:
            left  = list(reversed([t for t in sorted_q if t <= pos]))
            right = [t for t in sorted_q if t > pos]
            if left:
                result.append({"from": pos, "to": left[0], "note": "Moving toward track 0"})
            cur = left[0] if left else pos
            for t in left[1:]:
                result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t
            result.append({"from": cur, "to": 0, "note": "Reach end (track 0), reverse direction"}); cur = 0
            for t in right:
                result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t
        else:
            right = [t for t in sorted_q if t >= pos]
            left  = list(reversed([t for t in sorted_q if t < pos]))
            if right:
                result.append({"from": pos, "to": right[0], "note": "Moving toward higher tracks"})
            cur = right[0] if right else pos
            for t in right[1:]:
                result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t
            end = disk - 1
            result.append({"from": cur, "to": end, "note": f"Reach end (track {end}), reverse direction"}); cur = end
            for t in left:
                result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t

    elif algo == "cscan":
        sorted_q = sorted(remaining)
        right = [t for t in sorted_q if t >= pos]
        left  = [t for t in sorted_q if t < pos]
        cur = pos
        for t in right:
            result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t
        end = disk - 1
        result.append({"from": cur, "to": end, "note": f"Reach end (track {end})"}); cur = end
        result.append({"from": cur, "to": 0, "note": "Jump back to track 0 (no service)", "jump": True}); cur = 0
        for t in left:
            result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t

    elif algo == "look":
        sorted_q = sorted(remaining)
        go_up = (direction == "up")
        if not go_up:
            left  = list(reversed([t for t in sorted_q if t <= pos]))
            right = [t for t in sorted_q if t > pos]
            cur = pos
            for t in left:
                result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t
            if right:
                result.append({"from": cur, "to": right[0],
                                "note": f"No more requests left, reverse — service track {right[0]}"}); cur = right[0]
            for t in right[1:]:
                result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t
        else:
            right = [t for t in sorted_q if t >= pos]
            left  = list(reversed([t for t in sorted_q if t < pos]))
            cur = pos
            for t in right:
                result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t
            if left:
                result.append({"from": cur, "to": left[0],
                                "note": f"No more requests ahead, reverse — service track {left[0]}"}); cur = left[0]
            for t in left[1:]:
                result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t

    elif algo == "clook":
        sorted_q = sorted(remaining)
        right = [t for t in sorted_q if t >= pos]
        left  = [t for t in sorted_q if t < pos]
        cur = pos
        for t in right:
            result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t
        if left:
            result.append({"from": cur, "to": left[0],
                            "note": f"Jump to lowest request track {left[0]} (no service)", "jump": True}); cur = left[0]
            for t in left[1:]:
                result.append({"from": cur, "to": t, "note": f"Service track {t}"}); cur = t

    return result


# ─── Main App ──────────────────────────────────────────────────────────────────

class DiskSchedulingApp(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG)

        self.algo     = tk.StringVar(value="fcfs")
        self.steps    = []
        self.step_idx = 0
        self.total_mv = 0
        self.chart_ys = []       # y values for line chart
        self.chart_labels = []   # x labels
        self._user_zoomed = False  # True when user has manually zoomed/panned

        self._build_ui()
        self.reset_sim()

    # ── UI construction ─────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = tk.Frame(self, bg=BG, padx=16, pady=12)
        outer.pack(fill="both", expand=True)

        # ── Top controls ──────────────────────────────────────────────────────
        top = tk.Frame(outer, bg=BG)
        top.pack(fill="x", pady=(0, 10))

        # Head position
        f1 = tk.Frame(top, bg=BG)
        f1.pack(side="left", padx=(0, 12))
        tk.Label(f1, text="Initial head position", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.var_head = tk.StringVar(value="53")
        e1 = tk.Entry(f1, textvariable=self.var_head, width=8, relief="flat",
                      bg=BG, fg=TEXT, font=("Segoe UI", 10),
                      highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        e1.pack(ipady=4, padx=1)

        # Queue
        f2 = tk.Frame(top, bg=BG)
        f2.pack(side="left", padx=(0, 12))
        tk.Label(f2, text="Queue (comma-separated)", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.var_queue = tk.StringVar(value="98,183,37,122,14,124,65,67")
        e2 = tk.Entry(f2, textvariable=self.var_queue, width=26, relief="flat",
                      bg=BG, fg=TEXT, font=("Segoe UI", 10),
                      highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        e2.pack(ipady=4, padx=1)

        # Direction (shown for SCAN / LOOK)
        self.dir_frame = tk.Frame(top, bg=BG)
        # (packed later only when needed)
        tk.Label(self.dir_frame, text="Initial direction", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.var_dir = tk.StringVar(value="up")
        dir_combo = ttk.Combobox(self.dir_frame, textvariable=self.var_dir, state="readonly",
                                 width=22, font=("Segoe UI", 10))
        dir_combo["values"] = ["up", "down"]
        dir_combo.set("up")
        dir_combo.pack(ipady=2)
        # style tweak
        style = ttk.Style()
        style.configure("TCombobox", fieldbackground=BG, background=BG, foreground=TEXT)

        # Disk size
        f4 = tk.Frame(top, bg=BG)
        f4.pack(side="left", padx=(0, 0))
        tk.Label(f4, text="Disk size (tracks)", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.var_disk = tk.StringVar(value="200")
        e4 = tk.Entry(f4, textvariable=self.var_disk, width=7, relief="flat",
                      bg=BG, fg=TEXT, font=("Segoe UI", 10),
                      highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        e4.pack(ipady=4, padx=1)

        # ── Algorithm buttons ──────────────────────────────────────────────────
        algo_row = tk.Frame(outer, bg=BG)
        algo_row.pack(fill="x", pady=(0, 10))

        self._algo_btns = {}
        for name in ["fcfs", "sstf", "scan", "cscan", "look", "clook"]:
            b = tk.Button(algo_row, text=name.upper(), font=("Segoe UI", 9),
                          relief="flat", cursor="hand2",
                          padx=10, pady=4,
                          command=lambda n=name: self._select_algo(n))
            b.pack(side="left", padx=(0, 5))
            self._algo_btns[name] = b
        self._select_algo("fcfs", init=True)

        # ── Action buttons ─────────────────────────────────────────────────────
        act_row = tk.Frame(outer, bg=BG)
        act_row.pack(fill="x", pady=(0, 12))

        self.btn_start = tk.Button(act_row, text="▶  Start", font=("Segoe UI", 10),
                                   relief="flat", cursor="hand2", padx=14, pady=5,
                                   bg=INFO_BG, fg=INFO_TEXT,
                                   activebackground=INFO_BG, activeforeground=INFO_TEXT,
                                   command=self.start_sim)
        self.btn_start.pack(side="left", padx=(0, 7))

        self.btn_step = tk.Button(act_row, text="→  Next step", font=("Segoe UI", 10),
                                  relief="flat", cursor="hand2", padx=14, pady=5,
                                  bg=BG2, fg=TEXT,
                                  activebackground=BG2, activeforeground=TEXT,
                                  state="disabled",
                                  command=self.do_step)
        self.btn_step.pack(side="left", padx=(0, 7))

        self.btn_reset = tk.Button(act_row, text="↺  Reset", font=("Segoe UI", 10),
                                   relief="flat", cursor="hand2", padx=14, pady=5,
                                   bg=BG2, fg=TEXT,
                                   activebackground=BG2, activeforeground=TEXT,
                                   command=self.reset_sim)
        self.btn_reset.pack(side="left")

        # ── Stats row ──────────────────────────────────────────────────────────
        stats_row = tk.Frame(outer, bg=BG)
        stats_row.pack(fill="x", pady=(0, 10))
        stats_row.columnconfigure((0, 1, 2, 3), weight=1, uniform="stat")

        self.stat_vars = {
            "head":  tk.StringVar(value="—"),
            "step":  tk.StringVar(value="—"),
            "move":  tk.StringVar(value="—"),
            "total": tk.StringVar(value="0"),
        }
        labels = ["Current track", "Step", "Movement this step", "Total head movement"]
        keys   = ["head", "step", "move", "total"]
        for col, (lbl, key) in enumerate(zip(labels, keys)):
            card = tk.Frame(stats_row, bg=BG2,
                            highlightthickness=1, highlightbackground=BORDER)
            card.grid(row=0, column=col, padx=(0, 8) if col < 3 else 0, sticky="nsew")
            tk.Label(card, text=lbl, bg=BG2, fg=TEXT2,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(8, 0))
            tk.Label(card, textvariable=self.stat_vars[key], bg=BG2, fg=TEXT,
                     font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=10, pady=(0, 8))

        # ── Step info label ────────────────────────────────────────────────────
        self.step_info_var = tk.StringVar(value="Configure settings and press Start.")
        tk.Label(outer, textvariable=self.step_info_var, bg=BG, fg=TEXT2,
                 font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=(0, 8))

        # ── Chart ──────────────────────────────────────────────────────────────
        chart_frame = tk.Frame(outer, bg=BG, height=310)
        chart_frame.pack(fill="x", pady=(0, 8))
        chart_frame.pack_propagate(False)

        self.fig = Figure(figsize=(8, 2.8), dpi=96, facecolor=BG)
        self.ax  = self.fig.add_subplot(111, facecolor=BG)
        self._style_axes()
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().configure(bg=BG, highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Zoom/pan toolbar (matplotlib's built-in NavigationToolbar)
        toolbar_frame = tk.Frame(chart_frame, bg=BG2)
        toolbar_frame.pack(fill="x", side="bottom")
        self._toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame, pack_toolbar=False)
        self._toolbar.config(bg=BG2)
        for child in self._toolbar.winfo_children():
            try:
                child.config(bg=BG2)
            except Exception:
                pass
        self._toolbar.pack(side="left")

        # Reset-view button (auto-fit)
        tk.Button(toolbar_frame, text="⤢ Auto-fit", font=("Segoe UI", 8),
                  bg=BG2, fg=TEXT2, relief="flat", cursor="hand2",
                  padx=6, pady=2,
                  command=self._autofit_chart).pack(side="right", padx=4, pady=2)

        # Track when user manually zooms/pans so we don't override their view
        self.canvas.mpl_connect("button_release_event", self._on_chart_interact)
        self.canvas.mpl_connect("scroll_event",         self._on_chart_interact)

        # ── Step table ─────────────────────────────────────────────────────────
        table_frame = tk.Frame(outer, bg=BG)
        table_frame.pack(fill="both", expand=True)

        cols = ("Step", "From", "To", "Distance", "Cumulative")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=8)
        for c in cols:
            self.tree.heading(c, text=c, anchor="w")
            self.tree.column(c, width=100, anchor="w", stretch=True)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=BG, fieldbackground=BG, foreground=TEXT,
                        rowheight=26, font=("Segoe UI", 10), borderwidth=0)
        style.configure("Treeview.Heading",
                        background=BG, foreground=TEXT2, font=("Segoe UI", 9),
                        relief="flat", borderwidth=0)
        style.map("Treeview", background=[("selected", INFO_BG)],
                  foreground=[("selected", INFO_TEXT)])
        style.configure("Treeview", rowheight=26)

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── Helpers ─────────────────────────────────────────────────────────────────

    def _on_chart_interact(self, event):
        """Mark that user has manually zoomed/panned so auto-extend is suppressed."""
        # Only flag when zoom or pan tool is active (not the default pointer)
        mode = self._toolbar.mode
        if mode in ("zoom rect", "pan/zoom"):
            self._user_zoomed = True

    def _autofit_chart(self):
        """Reset to full auto-fit view."""
        self._user_zoomed = False
        if self.chart_ys:
            xs = list(range(len(self.chart_ys)))
            self.ax.set_xlim(-0.5, max(len(xs) - 0.5, 1))
            self.ax.set_ylim(0, self._disk - 1)
            self.canvas.draw_idle()

    def _style_axes(self):
        ax = self.ax
        ax.set_xlabel("Step", color=TEXT2, fontsize=10)
        ax.set_ylabel("Track number", color=TEXT2, fontsize=10)
        ax.tick_params(colors=TEXT2, labelsize=9)
        ax.spines[:].set_color(BORDER)
        ax.xaxis.label.set_color(TEXT2)
        ax.yaxis.label.set_color(TEXT2)
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.set_facecolor(BG)
        self.fig.patch.set_facecolor(BG)
        self.fig.subplots_adjust(left=0.07, right=0.99, top=0.95, bottom=0.18)

    def _select_algo(self, name, init=False):
        self.algo.set(name)
        for n, b in self._algo_btns.items():
            if n == name:
                b.configure(bg=INFO_BG, fg=INFO_TEXT,
                            activebackground=INFO_BG, activeforeground=INFO_TEXT)
            else:
                b.configure(bg=BG2, fg=TEXT2,
                            activebackground=BG2, activeforeground=TEXT2)
        needs_dir = name in ("scan", "look")
        if not init:
            if needs_dir:
                self.dir_frame.pack(side="left", padx=(0, 12))
            else:
                self.dir_frame.pack_forget()
            self.reset_sim()

    def _parse_inputs(self):
        try:
            head = int(self.var_head.get())
        except ValueError:
            head = 53
        raw = self.var_queue.get().split(",")
        queue = [int(s.strip()) for s in raw if s.strip().lstrip("-").isdigit()]
        try:
            disk = int(self.var_disk.get())
        except ValueError:
            disk = 200
        direction = self.var_dir.get()
        return head, queue, direction, disk

    # ── Simulation control ───────────────────────────────────────────────────────

    def start_sim(self):
        head, queue, direction, disk = self._parse_inputs()
        if not queue:
            return
        self.steps    = build_steps(head, queue, direction, disk, self.algo.get())
        self.step_idx = 0
        self.total_mv = 0

        self.stat_vars["head"].set(str(head))
        self.stat_vars["step"].set(f"0 / {len(self.steps)}")
        self.stat_vars["move"].set("—")
        self.stat_vars["total"].set("0")
        self.step_info_var.set('Press "Next step" to advance.')

        self.btn_step.configure(state="normal")
        self.btn_start.configure(state="disabled")

        for row in self.tree.get_children():
            self.tree.delete(row)

        self._init_chart(head, disk)

    def do_step(self):
        if self.step_idx >= len(self.steps):
            return
        s = self.steps[self.step_idx]
        dist = abs(s["to"] - s["from"])
        self.total_mv += dist
        self.step_idx += 1

        self.stat_vars["head"].set(str(s["to"]))
        self.stat_vars["step"].set(f"{self.step_idx} / {len(self.steps)}")
        jump_note = " (jump, not counted for C-SCAN/C-LOOK return)" if s.get("jump") else ""
        self.stat_vars["move"].set(f"{dist}{jump_note} tracks")
        self.stat_vars["total"].set(f"{self.total_mv} tracks")
        self.step_info_var.set(s["note"])

        # Table: un-highlight previous, add new
        for row in self.tree.get_children():
            self.tree.item(row, tags=("done",))
        self.tree.tag_configure("done",   foreground=TEXT2, background=BG)
        self.tree.tag_configure("current", foreground=INFO_TEXT, background=INFO_BG)

        iid = self.tree.insert("", "end",
                               values=(self.step_idx, s["from"], s["to"], dist, self.total_mv),
                               tags=("current",))
        self.tree.see(iid)

        # Chart update
        self._update_chart(s)

        if self.step_idx >= len(self.steps):
            self.btn_step.configure(state="disabled")
            self.step_info_var.set(f"✓ Done! Total head movement: {self.total_mv} tracks.")

    def reset_sim(self):
        self.steps    = []
        self.step_idx = 0
        self.total_mv = 0
        self.chart_ys     = []
        self.chart_labels = []

        self.stat_vars["head"].set("—")
        self.stat_vars["step"].set("—")
        self.stat_vars["move"].set("—")
        self.stat_vars["total"].set("0")
        self.step_info_var.set("Configure settings and press Start.")

        self.btn_step.configure(state="disabled")
        self.btn_start.configure(state="normal")

        for row in self.tree.get_children():
            self.tree.delete(row)

        self.ax.clear()
        self._style_axes()
        self._user_zoomed = False
        self.canvas.draw_idle()

    # ── Chart helpers ────────────────────────────────────────────────────────────

    def _init_chart(self, head, disk):
        self.chart_ys     = [head]
        self.chart_labels = ["Start"]
        self._disk = disk
        self._user_zoomed = False

        self.ax.clear()
        self._style_axes()
        self.ax.set_ylim(0, disk - 1)
        self.ax.set_xlim(-0.5, max(0.5, len(self.steps) + 0.5))
        self.ax.set_xticks(range(len(self.chart_labels)))
        self.ax.set_xticklabels(self.chart_labels, fontsize=8)
        self.ax.plot([0], [head], "o-", color=ACCENT, linewidth=1.8,
                     markersize=5, markerfacecolor=ACCENT)
        self.ax.grid(True, color="#e0e0e0", linewidth=0.5, linestyle="-")
        self.fig.tight_layout(pad=0.6)
        self.canvas.draw()

    def _update_chart(self, step):
        if step.get("jump"):
            self.chart_ys.append(float("nan"))
            self.chart_labels.append("↩")

        self.chart_ys.append(step["to"])
        self.chart_labels.append(f"Step {self.step_idx}")

        xs = list(range(len(self.chart_ys)))

        # Save current view limits if user has zoomed/panned
        if self._user_zoomed:
            saved_xlim = self.ax.get_xlim()
            saved_ylim = self.ax.get_ylim()
        else:
            saved_xlim = None
            saved_ylim = None

        self.ax.clear()
        self._style_axes()

        # Rotate labels if there are many
        rot = 45 if len(self.chart_labels) > 10 else 0
        self.ax.set_xticks(xs)
        self.ax.set_xticklabels(self.chart_labels, fontsize=7 if len(xs) > 15 else 8,
                                rotation=rot, ha="right" if rot else "center")
        self.ax.grid(True, color="#e0e0e0", linewidth=0.5)

        # Plot segments, breaking on NaN for jumps
        seg_x, seg_y = [], []
        for x, y in zip(xs, self.chart_ys):
            if math.isnan(y):
                if len(seg_x) > 1:
                    self.ax.plot(seg_x, seg_y, "-", color=ACCENT, linewidth=1.8)
                seg_x, seg_y = [], []
            else:
                seg_x.append(x)
                seg_y.append(y)
        if seg_x:
            self.ax.plot(seg_x, seg_y, "o-", color=ACCENT, linewidth=1.8,
                         markersize=4, markerfacecolor=ACCENT)

        if saved_xlim is not None:
            # Restore zoom but auto-extend x if new data is beyond right edge
            new_xmax = max(len(xs) - 0.5, 1)
            new_xlim = (saved_xlim[0], max(saved_xlim[1], new_xmax))
            self.ax.set_xlim(new_xlim)
            self.ax.set_ylim(saved_ylim)
        else:
            # Auto-fit: show all data
            self.ax.set_xlim(-0.5, max(len(xs) - 0.5, 1))
            self.ax.set_ylim(0, self._disk - 1)

        self.fig.tight_layout(pad=0.6)
        self.canvas.draw_idle()


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Disk Scheduling Simulator")
    root.minsize(780, 720)
    root.configure(bg=BG)
    app = DiskSchedulingApp(root)
    app.pack(fill="both", expand=True)
    root.mainloop()