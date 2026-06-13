"""
Deadlock backend — Banker's avoidance, detection, wait-for graph,
resource allocation graph, and circular-wait prevention.

UI-free module for use by the tkinter front end.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


# ── Example presets (for UI dropdowns / demos) ───────────────────────────────

BANKER_EXAMPLE = {
    "name": "Classic 5×3 (safe)",
    "num_processes": 5,
    "num_resources": 3,
    "allocation": [
        [0, 1, 0],
        [2, 0, 0],
        [3, 0, 2],
        [2, 1, 1],
        [0, 0, 2],
    ],
    "max_demand": [
        [7, 5, 3],
        [3, 2, 2],
        [9, 0, 2],
        [2, 2, 2],
        [4, 3, 3],
    ],
    "available": [7, 7, 8],
}

BANKER_UNSAFE_EXAMPLE = {
    "name": "Unsafe state demo",
    "num_processes": 3,
    "num_resources": 3,
    "allocation": [
        [0, 1, 0],
        [2, 0, 0],
        [3, 0, 2],
    ],
    "max_demand": [
        [7, 5, 3],
        [3, 2, 2],
        [9, 0, 2],
    ],
    "available": [0, 0, 0],
}

DETECTION_EXAMPLE = {
    "name": "Deadlocked system",
    "num_processes": 3,
    "num_resources": 3,
    "allocation": [
        [0, 1, 0],
        [2, 0, 0],
        [3, 0, 2],
    ],
    "current_request": [
        [0, 0, 0],
        [0, 2, 0],
        [6, 0, 0],
    ],
    "available": [0, 0, 0],
}

RAG_EXAMPLE = {
    "name": "Single-instance cycle (P0↔P1)",
    "num_processes": 2,
    "num_resources": 2,
    "holders": [0, 1],       # R0 held by P0, R1 held by P1
    "waiting": [1, 0],       # P0 waits for R1, P1 waits for R0
}


# ── Validation helpers ───────────────────────────────────────────────────────

def validate_matrix(matrix: list[list[int]], rows: int, cols: int, name: str) -> None:
    if len(matrix) != rows:
        raise ValueError(f"{name} must have {rows} rows.")
    for i, row in enumerate(matrix):
        if len(row) != cols:
            raise ValueError(f"{name} row {i} must have {cols} columns.")
        if any(v < 0 for v in row):
            raise ValueError(f"{name} values must be non-negative.")


def validate_vector(vector: list[int], length: int, name: str) -> None:
    if len(vector) != length:
        raise ValueError(f"{name} must have length {length}.")
    if any(v < 0 for v in vector):
        raise ValueError(f"{name} values must be non-negative.")


@dataclass
class SafetyResult:
    safe: bool
    sequence: list[int] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DetectionResult:
    deadlocked: bool
    processes: list[int] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RequestResult:
    granted: bool
    message: str
    safe: bool = False
    sequence: list[int] = field(default_factory=list)


# ── 1. Banker's Algorithm (deadlock avoidance) ───────────────────────────────

class DeadlockAvoidance:
    """
    Banker's algorithm for multiple resource instances.
    Proactively checks whether granting a request keeps the system in a safe state.
    """

    def __init__(
        self,
        num_processes: int,
        num_resources: int,
        allocation: list[list[int]],
        max_demand: list[list[int]],
        available: list[int],
    ):
        self.n = num_processes
        self.m = num_resources
        validate_matrix(allocation, self.n, self.m, "allocation")
        validate_matrix(max_demand, self.n, self.m, "max_demand")
        validate_vector(available, self.m, "available")

        for i in range(self.n):
            for j in range(self.m):
                if allocation[i][j] > max_demand[i][j]:
                    raise ValueError(
                        f"allocation[{i}][{j}] cannot exceed max_demand[{i}][{j}]."
                    )

        total_available = available[:]
        for i in range(self.n):
            for j in range(self.m):
                total_available[j] -= allocation[i][j]
        if any(v < 0 for v in total_available):
            raise ValueError("Total allocated resources exceed system resources.")

        self.allocation = deepcopy(allocation)
        self.max_demand = deepcopy(max_demand)
        self.available = available[:]
        self.need = self._compute_need()

    def _compute_need(self) -> list[list[int]]:
        return [
            [self.max_demand[i][j] - self.allocation[i][j] for j in range(self.m)]
            for i in range(self.n)
        ]

    def is_safe(self) -> SafetyResult:
        work = self.available[:]
        finish = [False] * self.n
        sequence: list[int] = []
        steps: list[dict[str, Any]] = []

        while len(sequence) < self.n:
            found = False
            for p in range(self.n):
                if finish[p]:
                    continue
                if all(self.need[p][j] <= work[j] for j in range(self.m)):
                    step = {
                        "process": p,
                        "action": "finish",
                        "work_before": work[:],
                        "need": self.need[p][:],
                        "allocation": self.allocation[p][:],
                    }
                    for j in range(self.m):
                        work[j] += self.allocation[p][j]
                    step["work_after"] = work[:]
                    steps.append(step)
                    sequence.append(p)
                    finish[p] = True
                    found = True
                    break

            if not found:
                return SafetyResult(
                    safe=False,
                    sequence=[],
                    steps=steps + [{"action": "unsafe", "unfinished": [p for p, f in enumerate(finish) if not f]}],
                )

        return SafetyResult(safe=True, sequence=sequence, steps=steps)

    def request_resources(self, process_id: int, request: list[int]) -> RequestResult:
        if not 0 <= process_id < self.n:
            return RequestResult(False, f"Invalid process id {process_id}.")

        validate_vector(request, self.m, "request")

        if any(request[j] > self.need[process_id][j] for j in range(self.m)):
            return RequestResult(
                False,
                f"Denied: request exceeds need for P{process_id}.",
            )

        if any(request[j] > self.available[j] for j in range(self.m)):
            return RequestResult(
                False,
                f"Denied: not enough available resources for P{process_id}.",
            )

        for j in range(self.m):
            self.available[j] -= request[j]
            self.allocation[process_id][j] += request[j]
            self.need[process_id][j] -= request[j]

        result = self.is_safe()
        if result.safe:
            seq_str = " → ".join(f"P{p}" for p in result.sequence)
            return RequestResult(
                True,
                f"Granted to P{process_id}. System remains safe: {seq_str}.",
                safe=True,
                sequence=result.sequence,
            )

        for j in range(self.m):
            self.available[j] += request[j]
            self.allocation[process_id][j] -= request[j]
            self.need[process_id][j] += request[j]

        return RequestResult(
            False,
            f"Denied: granting request to P{process_id} would leave an unsafe state.",
            safe=False,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "allocation": deepcopy(self.allocation),
            "max_demand": deepcopy(self.max_demand),
            "available": self.available[:],
            "need": deepcopy(self.need),
        }


# ── 2. Deadlock detection (multiple instances) ─────────────────────────────────

class DeadlockDetection:
    """
    Deadlock detection for multiple resource instances.
    Uses current outstanding requests instead of max demand.
    """

    def __init__(
        self,
        num_processes: int,
        num_resources: int,
        allocation: list[list[int]],
        current_request: list[list[int]],
        available: list[int],
    ):
        self.n = num_processes
        self.m = num_resources
        validate_matrix(allocation, self.n, self.m, "allocation")
        validate_matrix(current_request, self.n, self.m, "current_request")
        validate_vector(available, self.m, "available")

        self.allocation = deepcopy(allocation)
        self.request = deepcopy(current_request)
        self.available = available[:]

    def detect_deadlock(self) -> DetectionResult:
        work = self.available[:]
        finish = [all(self.allocation[i][j] == 0 for j in range(self.m)) for i in range(self.n)]
        steps: list[dict[str, Any]] = []

        while True:
            found = False
            for p in range(self.n):
                if finish[p]:
                    continue
                if all(self.request[p][j] <= work[j] for j in range(self.m)):
                    step = {
                        "process": p,
                        "action": "release",
                        "work_before": work[:],
                        "request": self.request[p][:],
                        "allocation": self.allocation[p][:],
                    }
                    for j in range(self.m):
                        work[j] += self.allocation[p][j]
                    finish[p] = True
                    step["work_after"] = work[:]
                    steps.append(step)
                    found = True
                    break

            if not found:
                break

        deadlocked = [p for p in range(self.n) if not finish[p]]
        return DetectionResult(
            deadlocked=bool(deadlocked),
            processes=deadlocked,
            steps=steps,
        )


# ── 3. Wait-for graph (single-instance resources) ────────────────────────────

class WaitForGraph:
    """
    Cycle detection in a wait-for graph.
    With single-instance resources, a cycle ⟺ deadlock.
    """

    def __init__(self, num_processes: int):
        self.n = num_processes
        self.graph: dict[int, list[int]] = {i: [] for i in range(self.n)}

    def add_edge(self, waiting_process: int, holding_process: int) -> None:
        if waiting_process == holding_process:
            return
        if holding_process not in self.graph[waiting_process]:
            self.graph[waiting_process].append(holding_process)

    def clear(self) -> None:
        self.graph = {i: [] for i in range(self.n)}

    def is_deadlocked(self) -> bool:
        return self.get_cycle() is not None

    def get_cycle(self) -> list[int] | None:
        visited: set[int] = set()
        stack: list[int] = []

        def dfs(node: int) -> list[int] | None:
            visited.add(node)
            stack.append(node)

            for neighbor in self.graph.get(node, []):
                if neighbor not in visited:
                    cycle = dfs(neighbor)
                    if cycle:
                        return cycle
                elif neighbor in stack:
                    start = stack.index(neighbor)
                    return stack[start:] + [neighbor]

            stack.pop()
            return None

        for node in range(self.n):
            if node not in visited:
                cycle = dfs(node)
                if cycle:
                    return cycle
        return None

    def to_edges(self) -> list[tuple[int, int]]:
        return [
            (src, dst)
            for src in range(self.n)
            for dst in self.graph[src]
        ]


# ── 4. Resource allocation graph ─────────────────────────────────────────────

class ResourceAllocationGraph:
    """
    Single-instance resource allocation graph (RAG).
    Builds a wait-for graph and detects cycles.
    """

    FREE = -1

    def __init__(self, num_processes: int, num_resources: int):
        self.num_processes = num_processes
        self.num_resources = num_resources
        self.holders = [self.FREE] * num_resources
        self.waiting = [self.FREE] * num_processes

    def assign(self, resource_id: int, process_id: int) -> None:
        if not 0 <= resource_id < self.num_resources:
            raise ValueError(f"Invalid resource id {resource_id}.")
        if not 0 <= process_id < self.num_processes:
            raise ValueError(f"Invalid process id {process_id}.")
        self.holders[resource_id] = process_id
        if self.waiting[process_id] == resource_id:
            self.waiting[process_id] = self.FREE

    def release(self, resource_id: int) -> None:
        if not 0 <= resource_id < self.num_resources:
            raise ValueError(f"Invalid resource id {resource_id}.")
        self.holders[resource_id] = self.FREE

    def request(self, process_id: int, resource_id: int) -> None:
        if not 0 <= process_id < self.num_processes:
            raise ValueError(f"Invalid process id {process_id}.")
        if not 0 <= resource_id < self.num_resources:
            raise ValueError(f"Invalid resource id {resource_id}.")
        self.waiting[process_id] = resource_id

    def clear_request(self, process_id: int) -> None:
        self.waiting[process_id] = self.FREE

    def build_wait_for_graph(self) -> WaitForGraph:
        wfg = WaitForGraph(self.num_processes)
        for p in range(self.num_processes):
            resource = self.waiting[p]
            if resource == self.FREE:
                continue
            holder = self.holders[resource]
            if holder != self.FREE and holder != p:
                wfg.add_edge(p, holder)
        return wfg

    def detect_deadlock(self) -> DetectionResult:
        wfg = self.build_wait_for_graph()
        cycle = wfg.get_cycle()
        if cycle is None:
            return DetectionResult(deadlocked=False, processes=[], steps=[])
        unique = []
        for p in cycle:
            if p not in unique:
                unique.append(p)
        return DetectionResult(deadlocked=True, processes=unique, steps=[{"cycle": cycle}])

    def snapshot(self) -> dict[str, Any]:
        return {
            "holders": self.holders[:],
            "waiting": self.waiting[:],
            "edges": self.build_wait_for_graph().to_edges(),
        }


# ── 5. Deadlock prevention (circular-wait elimination) ─────────────────────

class DeadlockPrevention:
    """
    Circular-wait prevention via strict resource ordering.
    Processes must request resources in increasing ID order.
    """

    def __init__(self, num_processes: int):
        self.n = num_processes
        self.highest_resource_held = {i: -1 for i in range(self.n)}

    def request_resource(self, process_id: int, resource_id: int) -> tuple[bool, str]:
        if not 0 <= process_id < self.n:
            return False, f"Invalid process id {process_id}."
        if resource_id < 0:
            return False, "Resource id must be non-negative."

        current_highest = self.highest_resource_held[process_id]
        if resource_id > current_highest:
            self.highest_resource_held[process_id] = resource_id
            return True, f"Granted: R{resource_id} assigned to P{process_id}."
        return (
            False,
            f"Denied: P{process_id} holds up to R{current_highest}; "
            f"cannot request R{resource_id} (violates resource ordering).",
        )

    def release_resource(self, process_id: int, resource_id: int) -> tuple[bool, str]:
        if not 0 <= process_id < self.n:
            return False, f"Invalid process id {process_id}."
        if self.highest_resource_held[process_id] == resource_id:
            self.highest_resource_held[process_id] = resource_id - 1
        return True, f"Released: P{process_id} released R{resource_id}."


# ── Convenience factories from presets ───────────────────────────────────────

def banker_from_preset(preset: dict | None = None) -> DeadlockAvoidance:
    data = preset or BANKER_EXAMPLE
    return DeadlockAvoidance(
        data["num_processes"],
        data["num_resources"],
        data["allocation"],
        data["max_demand"],
        data["available"],
    )


def detection_from_preset(preset: dict | None = None) -> DeadlockDetection:
    data = preset or DETECTION_EXAMPLE
    return DeadlockDetection(
        data["num_processes"],
        data["num_resources"],
        data["allocation"],
        data["current_request"],
        data["available"],
    )


def rag_from_preset(preset: dict | None = None) -> ResourceAllocationGraph:
    data = preset or RAG_EXAMPLE
    rag = ResourceAllocationGraph(data["num_processes"], data["num_resources"])
    for r, holder in enumerate(data["holders"]):
        if holder >= 0:
            rag.assign(r, holder)
    for p, resource in enumerate(data["waiting"]):
        if resource >= 0:
            rag.request(p, resource)
    return rag


# ── Tkinter UI ────────────────────────────────────────────────────────────────

UI_BG      = "#1E1E1E"
UI_BG2     = "#2A2A2A"
UI_BG3     = "#333333"
UI_TEXT    = "#E8E6E3"
UI_TEXT2   = "#A8A6A3"
UI_TEXT3   = "#6B6967"
UI_BORDER  = "#3A3A3A"
UI_BLUE    = "#185FA5"
UI_GREEN   = "#1D9E75"
UI_RED     = "#C0392B"
UI_ORANGE  = "#D85A30"
UI_YELLOW  = "#C8A84B"
UI_WHITE   = "#FFFFFF"
PCOLS      = ["#5B8DF5", "#F5A023", "#22C55E", "#F05070", "#A855F7",
              "#EAB308", "#06B6D4", "#F97316"]

TAB_DESCS = {
    "banker": (
        "Banker's algorithm — checks whether the system is in a safe state before "
        "granting resource requests. A safe sequence means all processes can finish."
    ),
    "detection": (
        "Deadlock detection — simulates resource release to see which processes can "
        "still complete. Remaining processes are deadlocked."
    ),
    "rag": (
        "Resource allocation graph — single-instance resources. A cycle in the "
        "wait-for graph means the system is deadlocked."
    ),
    "prevention": (
        "Circular-wait prevention — resources must be requested in strictly "
        "increasing ID order to prevent cycles."
    ),
}


def _parse_int_list(text: str, expected: int | None = None, name: str = "value") -> list[int]:
    parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    if not parts:
        raise ValueError(f"Enter comma-separated integers for {name}.")
    try:
        values = [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"{name} must contain integers only.") from exc
    if expected is not None and len(values) != expected:
        raise ValueError(f"{name} must have exactly {expected} values.")
    return values


def _matrix_to_text(matrix: list[list[int]]) -> str:
    return "\n".join(", ".join(str(v) for v in row) for row in matrix)


def _text_to_matrix(text: str, rows: int, cols: int, name: str) -> list[list[int]]:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) != rows:
        raise ValueError(f"{name} must have {rows} rows.")
    matrix = []
    for i, line in enumerate(lines):
        row = _parse_int_list(line, expected=cols, name=f"{name} row {i}")
        matrix.append(row)
    return matrix


class DeadlockApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Deadlock Simulator")
        self.configure(bg=UI_BG)
        self.minsize(900, 680)
        self.geometry("980x740")

        self.tab = "banker"
        self.banker: DeadlockAvoidance | None = None
        self.detector: DeadlockDetection | None = None
        self.rag: ResourceAllocationGraph | None = None
        self.prevention = DeadlockPrevention(3)

        self.safety_steps: list[dict[str, Any]] = []
        self.safety_idx = -1
        self.det_steps: list[dict[str, Any]] = []
        self.det_idx = -1

        self._build_ui()
        self._load_banker_preset(BANKER_EXAMPLE)
        self._load_detection_preset(DETECTION_EXAMPLE)
        self._load_rag_preset(RAG_EXAMPLE)

    # ── shared chrome ────────────────────────────────────────────────────────

    def _build_ui(self):
        top = tk.Frame(self, bg=UI_BG, padx=18, pady=14)
        
        
        top.pack(fill="x")

        tk.Label(top, text="Deadlock Simulator", bg=UI_BG, fg=UI_TEXT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(top, text="Avoidance, detection, resource allocation graph, and prevention",
                 bg=UI_BG, fg=UI_TEXT2, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 8))

        tab_row = tk.Frame(top, bg=UI_BG)
        tab_row.pack(fill="x", pady=(0, 8))
        self.tab_btns: dict[str, tk.Button] = {}
        for key, label in [
            ("banker", "Banker's (Avoidance)"),
            ("detection", "Detection"),
            ("rag", "RAG / Wait-For"),
            ("prevention", "Prevention"),
        ]:
            btn = tk.Button(
                tab_row, text=label, font=("Segoe UI", 10),
                relief="flat", padx=12, pady=5, cursor="hand2",
                command=lambda k=key: self._set_tab(k),
            )
            btn.pack(side="left", padx=(0, 6))
            self.tab_btns[key] = btn

        desc_f = tk.Frame(top, bg=UI_BG2)
        desc_f.pack(fill="x")
        tk.Frame(desc_f, bg=UI_BLUE, width=3).pack(side="left", fill="y")
        self.desc_var = tk.StringVar(value=TAB_DESCS["banker"])
        tk.Label(desc_f, textvariable=self.desc_var, bg=UI_BG2, fg=UI_TEXT2,
                 font=("Segoe UI", 10), wraplength=900, justify="left",
                 padx=10, pady=8).pack(side="left", fill="x", expand=True)

        self.body = tk.Frame(self, bg=UI_BG, padx=18, pady=8)
        self.body.pack(fill="both", expand=True)

        self.panels: dict[str, tk.Frame] = {}
        for key in ("banker", "detection", "rag", "prevention"):
            frame = tk.Frame(self.body, bg=UI_BG)
            self.panels[key] = frame

        self._build_banker_panel()
        self._build_detection_panel()
        self._build_rag_panel()
        self._build_prevention_panel()
        self._style_tabs()
        self.panels["banker"].pack(fill="both", expand=True)

    def _style_tabs(self):
        for key, btn in self.tab_btns.items():
            active = key == self.tab
            btn.configure(
                bg=UI_BG3 if active else UI_BG,
                fg=UI_TEXT if active else UI_TEXT2,
            )

    def _set_tab(self, key: str):
        self.tab = key
        self.desc_var.set(TAB_DESCS[key])
        for frame in self.panels.values():
            frame.pack_forget()
        self.panels[key].pack(fill="both", expand=True)
        self._style_tabs()

    def _info_banner(self, parent, var: tk.StringVar) -> tk.Label:
        box = tk.Frame(parent, bg=UI_BG2, highlightthickness=1, highlightbackground=UI_BORDER)
        box.pack(fill="x", pady=(0, 8))
        tk.Frame(box, bg=UI_BLUE, width=3).pack(side="left", fill="y")
        lbl = tk.Label(box, textvariable=var, bg=UI_BG2, fg=UI_TEXT,
                       font=("Segoe UI", 10), wraplength=860, justify="left",
                       padx=10, pady=8, anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        return lbl

    def _styled_tree(self, parent, cols: list[str], widths: list[int], height: int = 6):
        wrap = tk.Frame(parent, bg=UI_BORDER, padx=1, pady=1)
        wrap.pack(fill="x", pady=(0, 8))
        tree = ttk.Treeview(wrap, columns=cols, show="headings", height=height)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Dead.Treeview", background=UI_BG2, fieldbackground=UI_BG2,
                        foreground=UI_TEXT, rowheight=24, font=("Segoe UI", 10), borderwidth=0)
        style.configure("Dead.Treeview.Heading", background=UI_BG3, foreground=UI_TEXT2,
                        font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Dead.Treeview", background=[("selected", UI_BLUE)],
                  foreground=[("selected", UI_WHITE)])
        tree.configure(style="Dead.Treeview")
        for col, w in zip(cols, widths):
            tree.heading(col, text=col, anchor="w")
            tree.column(col, width=w, minwidth=w, stretch=False, anchor="w")
        tree.pack(fill="x")
        return tree

    def _entry(self, parent, var: tk.StringVar, width: int = 10) -> tk.Entry:
        e = tk.Entry(parent, textvariable=var, width=width, bg=UI_BG2, fg=UI_TEXT,
                     insertbackground=UI_TEXT, relief="flat",
                     highlightthickness=1, highlightbackground=UI_BORDER,
                     highlightcolor=UI_BLUE, font=("Segoe UI", 10))
        e.pack(side="left", padx=(0, 8))
        return e

    # ── Banker's tab ─────────────────────────────────────────────────────────

    def _build_banker_panel(self):
        p = self.panels["banker"]
        self.banker_info = tk.StringVar(value="Load a preset or edit matrices, then run a safety check.")

        ctrl = tk.Frame(p, bg=UI_BG)
        ctrl.pack(fill="x", pady=(0, 8))

        tk.Label(ctrl, text="Preset", bg=UI_BG, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
        self.banker_preset = tk.StringVar(value=BANKER_EXAMPLE["name"])
        cb = ttk.Combobox(ctrl, textvariable=self.banker_preset, state="readonly", width=28,
                          values=[BANKER_EXAMPLE["name"], BANKER_UNSAFE_EXAMPLE["name"]])
        cb.pack(side="left", padx=(6, 12))
        cb.bind("<<ComboboxSelected>>", lambda _e: self._on_banker_preset())

        tk.Button(ctrl, text="Apply preset", bg=UI_BG3, fg=UI_TEXT, relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  command=self._on_banker_preset).pack(side="left", padx=(0, 8))
        tk.Button(ctrl, text="Build model", bg=UI_BLUE, fg=UI_WHITE, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  command=self._build_banker_model).pack(side="left", padx=(0, 8))
        tk.Button(ctrl, text="Check safety", bg=UI_GREEN, fg=UI_WHITE, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  command=self._run_banker_safety).pack(side="left")

        self._info_banner(p, self.banker_info)

        dims = tk.Frame(p, bg=UI_BG)
        dims.pack(fill="x", pady=(0, 8))
        self.b_n_var = tk.IntVar(value=5)
        self.b_m_var = tk.IntVar(value=3)
        for label, var in [("Processes", self.b_n_var), ("Resources", self.b_m_var)]:
            tk.Label(dims, text=label, bg=UI_BG, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
            tk.Spinbox(dims, from_=1, to=8, width=4, textvariable=var,
                       font=("Segoe UI", 10), command=self._resize_banker_fields).pack(side="left", padx=(4, 12))

        tk.Label(dims, text="Available", bg=UI_BG, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
        self.b_avail_var = tk.StringVar(value="3, 3, 2")
        self._entry(dims, self.b_avail_var, width=16)

        grid = tk.Frame(p, bg=UI_BG)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        left = tk.Frame(grid, bg=UI_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(left, text="ALLOCATION (rows = processes)", bg=UI_BG, fg=UI_TEXT2,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.b_alloc_text = tk.Text(left, height=7, bg=UI_BG2, fg=UI_TEXT, insertbackground=UI_TEXT,
                                    relief="flat", highlightthickness=1, highlightbackground=UI_BORDER,
                                    font=("Courier New", 10))
        self.b_alloc_text.pack(fill="both", expand=True, pady=(4, 8))

        right = tk.Frame(grid, bg=UI_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(right, text="MAX DEMAND", bg=UI_BG, fg=UI_TEXT2,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.b_max_text = tk.Text(right, height=7, bg=UI_BG2, fg=UI_TEXT, insertbackground=UI_TEXT,
                                  relief="flat", highlightthickness=1, highlightbackground=UI_BORDER,
                                  font=("Courier New", 10))
        self.b_max_text.pack(fill="both", expand=True, pady=(4, 8))

        bottom = tk.Frame(p, bg=UI_BG)
        bottom.pack(fill="x", pady=(8, 0))

        req_row = tk.Frame(bottom, bg=UI_BG2, highlightthickness=1, highlightbackground=UI_BORDER)
        req_row.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(req_row, bg=UI_BG2, padx=10, pady=8)
        inner.pack(fill="x")
        tk.Label(inner, text="Try resource request", bg=UI_BG2, fg=UI_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 12))
        tk.Label(inner, text="Process", bg=UI_BG2, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
        self.b_req_p_var = tk.StringVar(value="1")
        self._entry(inner, self.b_req_p_var, width=4)
        tk.Label(inner, text="Request vector", bg=UI_BG2, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
        self.b_req_vec_var = tk.StringVar(value="0, 2, 0")
        self._entry(inner, self.b_req_vec_var, width=14)
        tk.Button(inner, text="Request", bg=UI_ORANGE, fg=UI_WHITE, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  command=self._banker_request).pack(side="left")

        step_row = tk.Frame(bottom, bg=UI_BG)
        step_row.pack(fill="x")
        tk.Button(step_row, text="← Prev step", bg=UI_BG3, fg=UI_TEXT, relief="flat",
                  padx=8, pady=4, cursor="hand2",
                  command=lambda: self._banker_step(-1)).pack(side="left")
        tk.Button(step_row, text="Next step →", bg=UI_BG3, fg=UI_TEXT, relief="flat",
                  padx=8, pady=4, cursor="hand2",
                  command=lambda: self._banker_step(1)).pack(side="left", padx=(6, 0))
        self.b_step_lbl = tk.Label(step_row, text="Safety steps: —", bg=UI_BG, fg=UI_TEXT2,
                                   font=("Segoe UI", 9))
        self.b_step_lbl.pack(side="left", padx=10)

        self.banker_step_tree = self._styled_tree(
            bottom, ["Step", "Process", "Work before", "Need", "Work after"], [50, 70, 180, 180, 180], height=5
        )
        self.banker_state_tree = self._styled_tree(
            bottom, ["Process", "Allocation", "Max", "Need", "Available"], [70, 180, 180, 180, 120], height=6
        )

    def _resize_banker_fields(self):
        n, m = self.b_n_var.get(), self.b_m_var.get()
        self.b_avail_var.set(", ".join(["0"] * m))

    def _load_banker_preset(self, preset: dict):
        self.b_n_var.set(preset["num_processes"])
        self.b_m_var.set(preset["num_resources"])
        self.b_avail_var.set(", ".join(str(v) for v in preset["available"]))
        self.b_alloc_text.delete("1.0", "end")
        self.b_alloc_text.insert("1.0", _matrix_to_text(preset["allocation"]))
        self.b_max_text.delete("1.0", "end")
        self.b_max_text.insert("1.0", _matrix_to_text(preset["max_demand"]))

    def _on_banker_preset(self):
        name = self.banker_preset.get()
        preset = BANKER_UNSAFE_EXAMPLE if "Unsafe" in name else BANKER_EXAMPLE
        self._load_banker_preset(preset)
        self._build_banker_model()

    def _read_banker_inputs(self):
        n, m = self.b_n_var.get(), self.b_m_var.get()
        allocation = _text_to_matrix(self.b_alloc_text.get("1.0", "end"), n, m, "Allocation")
        max_demand = _text_to_matrix(self.b_max_text.get("1.0", "end"), n, m, "Max demand")
        available = _parse_int_list(self.b_avail_var.get(), expected=m, name="Available")
        return n, m, allocation, max_demand, available

    def _build_banker_model(self):
        try:
            n, m, allocation, max_demand, available = self._read_banker_inputs()
            self.banker = DeadlockAvoidance(n, m, allocation, max_demand, available)
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        self._refresh_banker_state_table()
        self.banker_info.set("Model built. Run a safety check or try a resource request.")
        self.safety_steps = []
        self.safety_idx = -1
        self.b_step_lbl.config(text="Safety steps: —")
        for row in self.banker_step_tree.get_children():
            self.banker_step_tree.delete(row)

    def _refresh_banker_state_table(self):
        if not self.banker:
            return
        for row in self.banker_state_tree.get_children():
            self.banker_state_tree.delete(row)
        avail = ", ".join(str(v) for v in self.banker.available)
        for i in range(self.banker.n):
            self.banker_state_tree.insert(
                "", "end",
                values=(
                    f"P{i}",
                    str(self.banker.allocation[i]),
                    str(self.banker.max_demand[i]),
                    str(self.banker.need[i]),
                    avail if i == 0 else "",
                ),
            )

    def _run_banker_safety(self):
        if not self.banker:
            self._build_banker_model()
        if not self.banker:
            return
        result = self.banker.is_safe()
        self.safety_steps = result.steps
        self.safety_idx = len(self.safety_steps) - 1 if self.safety_steps else -1
        self._render_banker_steps()
        if result.safe:
            seq = " → ".join(f"P{p}" for p in result.sequence)
            self.banker_info.set(f"✓ Safe state. Safe sequence: {seq}")
        else:
            unfinished = result.steps[-1].get("unfinished", []) if result.steps else []
            procs = ", ".join(f"P{p}" for p in unfinished) or "unknown"
            self.banker_info.set(f"✗ Unsafe state. Cannot finish: {procs}")

    def _render_banker_steps(self):
        for row in self.banker_step_tree.get_children():
            self.banker_step_tree.delete(row)
        for i, step in enumerate(self.safety_steps):
            if step.get("action") == "unsafe":
                self.banker_step_tree.insert("", "end", values=(
                    i + 1, "—", "—", f"Blocked: {step.get('unfinished')}", "—",
                ))
            else:
                self.banker_step_tree.insert("", "end", values=(
                    i + 1,
                    f"P{step['process']}",
                    str(step["work_before"]),
                    str(step["need"]),
                    str(step["work_after"]),
                ))
        if 0 <= self.safety_idx < len(self.safety_steps):
            rows = self.banker_step_tree.get_children()
            if rows:
                self.banker_step_tree.selection_set(rows[self.safety_idx])
                self.banker_step_tree.see(rows[self.safety_idx])
            self.b_step_lbl.config(text=f"Safety step {self.safety_idx + 1} / {len(self.safety_steps)}")
        else:
            self.b_step_lbl.config(text="Safety steps: —")

    def _banker_step(self, delta: int):
        if not self.safety_steps:
            return
        self.safety_idx = max(0, min(len(self.safety_steps) - 1, self.safety_idx + delta))
        self._render_banker_steps()

    def _banker_request(self):
        if not self.banker:
            self._build_banker_model()
        if not self.banker:
            return
        try:
            pid = int(self.b_req_p_var.get().strip())
            request = _parse_int_list(self.b_req_vec_var.get(), expected=self.banker.m, name="Request")
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        result = self.banker.request_resources(pid, request)
        self._refresh_banker_state_table()
        prefix = "✓" if result.granted else "✗"
        self.banker_info.set(f"{prefix} {result.message}")
        if result.granted:
            self._run_banker_safety()

    # ── Detection tab ────────────────────────────────────────────────────────

    def _build_detection_panel(self):
        p = self.panels["detection"]
        self.det_info = tk.StringVar(value="Configure the system state and run deadlock detection.")

        ctrl = tk.Frame(p, bg=UI_BG)
        ctrl.pack(fill="x", pady=(0, 8))
        tk.Button(ctrl, text="Load example", bg=UI_BG3, fg=UI_TEXT, relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  command=lambda: self._load_detection_preset(DETECTION_EXAMPLE)).pack(side="left", padx=(0, 8))
        tk.Button(ctrl, text="Build model", bg=UI_BLUE, fg=UI_WHITE, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  command=self._build_detection_model).pack(side="left", padx=(0, 8))
        tk.Button(ctrl, text="Detect deadlock", bg=UI_RED, fg=UI_WHITE, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  command=self._run_detection).pack(side="left")

        self._info_banner(p, self.det_info)

        dims = tk.Frame(p, bg=UI_BG)
        dims.pack(fill="x", pady=(0, 8))
        self.d_n_var = tk.IntVar(value=3)
        self.d_m_var = tk.IntVar(value=3)
        for label, var in [("Processes", self.d_n_var), ("Resources", self.d_m_var)]:
            tk.Label(dims, text=label, bg=UI_BG, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
            tk.Spinbox(dims, from_=1, to=8, width=4, textvariable=var,
                       font=("Segoe UI", 10)).pack(side="left", padx=(4, 12))
        tk.Label(dims, text="Available", bg=UI_BG, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
        self.d_avail_var = tk.StringVar(value="0, 0, 0")
        self._entry(dims, self.d_avail_var, width=16)

        grid = tk.Frame(p, bg=UI_BG)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        left = tk.Frame(grid, bg=UI_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(left, text="ALLOCATION", bg=UI_BG, fg=UI_TEXT2,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.d_alloc_text = tk.Text(left, height=7, bg=UI_BG2, fg=UI_TEXT, insertbackground=UI_TEXT,
                                    relief="flat", highlightthickness=1, highlightbackground=UI_BORDER,
                                    font=("Courier New", 10))
        self.d_alloc_text.pack(fill="both", expand=True, pady=(4, 8))

        right = tk.Frame(grid, bg=UI_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(right, text="CURRENT REQUEST", bg=UI_BG, fg=UI_TEXT2,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.d_req_text = tk.Text(right, height=7, bg=UI_BG2, fg=UI_TEXT, insertbackground=UI_TEXT,
                                 relief="flat", highlightthickness=1, highlightbackground=UI_BORDER,
                                 font=("Courier New", 10))
        self.d_req_text.pack(fill="both", expand=True, pady=(4, 8))

        step_row = tk.Frame(p, bg=UI_BG)
        step_row.pack(fill="x", pady=(8, 0))
        tk.Button(step_row, text="← Prev", bg=UI_BG3, fg=UI_TEXT, relief="flat",
                  padx=8, pady=4, cursor="hand2",
                  command=lambda: self._det_step(-1)).pack(side="left")
        tk.Button(step_row, text="Next →", bg=UI_BG3, fg=UI_TEXT, relief="flat",
                  padx=8, pady=4, cursor="hand2",
                  command=lambda: self._det_step(1)).pack(side="left", padx=(6, 0))
        self.d_step_lbl = tk.Label(step_row, text="Detection steps: —", bg=UI_BG, fg=UI_TEXT2,
                                   font=("Segoe UI", 9))
        self.d_step_lbl.pack(side="left", padx=10)

        self.det_step_tree = self._styled_tree(
            p, ["Step", "Process", "Work before", "Request", "Work after"],
            [50, 70, 200, 200, 200], height=8
        )

    def _load_detection_preset(self, preset: dict):
        self.d_n_var.set(preset["num_processes"])
        self.d_m_var.set(preset["num_resources"])
        self.d_avail_var.set(", ".join(str(v) for v in preset["available"]))
        self.d_alloc_text.delete("1.0", "end")
        self.d_alloc_text.insert("1.0", _matrix_to_text(preset["allocation"]))
        self.d_req_text.delete("1.0", "end")
        self.d_req_text.insert("1.0", _matrix_to_text(preset["current_request"]))

    def _build_detection_model(self):
        try:
            n, m = self.d_n_var.get(), self.d_m_var.get()
            allocation = _text_to_matrix(self.d_alloc_text.get("1.0", "end"), n, m, "Allocation")
            current_request = _text_to_matrix(self.d_req_text.get("1.0", "end"), n, m, "Current request")
            available = _parse_int_list(self.d_avail_var.get(), expected=m, name="Available")
            self.detector = DeadlockDetection(n, m, allocation, current_request, available)
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        self.det_info.set("Model built. Run deadlock detection.")

    def _run_detection(self):
        if not self.detector:
            self._build_detection_model()
        if not self.detector:
            return
        result = self.detector.detect_deadlock()
        self.det_steps = result.steps
        self.det_idx = len(self.det_steps) - 1 if self.det_steps else -1
        self._render_det_steps()
        if result.deadlocked:
            procs = ", ".join(f"P{p}" for p in result.processes)
            self.det_info.set(f"✗ Deadlock detected. Deadlocked processes: {procs}")
            self.det_step_tree.tag_configure("dead", foreground=UI_RED)
        else:
            self.det_info.set("✓ No deadlock. All processes can complete.")

    def _render_det_steps(self):
        for row in self.det_step_tree.get_children():
            self.det_step_tree.delete(row)
        for i, step in enumerate(self.det_steps):
            self.det_step_tree.insert("", "end", values=(
                i + 1, f"P{step['process']}",
                str(step["work_before"]), str(step["request"]), str(step["work_after"]),
            ))
        if 0 <= self.det_idx < len(self.det_steps):
            rows = self.det_step_tree.get_children()
            self.det_step_tree.selection_set(rows[self.det_idx])
            self.det_step_tree.see(rows[self.det_idx])
            self.d_step_lbl.config(text=f"Step {self.det_idx + 1} / {len(self.det_steps)}")
        else:
            self.d_step_lbl.config(text="Detection steps: —")

    def _det_step(self, delta: int):
        if not self.det_steps:
            return
        self.det_idx = max(0, min(len(self.det_steps) - 1, self.det_idx + delta))
        self._render_det_steps()

    # ── RAG tab ──────────────────────────────────────────────────────────────

    def _build_rag_panel(self):
        p = self.panels["rag"]
        self.rag_info = tk.StringVar(value="Assign resource holders and waiting processes, then detect cycles.")

        ctrl = tk.Frame(p, bg=UI_BG)
        ctrl.pack(fill="x", pady=(0, 8))
        tk.Button(ctrl, text="Load example", bg=UI_BG3, fg=UI_TEXT, relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  command=lambda: self._load_rag_preset(RAG_EXAMPLE)).pack(side="left", padx=(0, 8))
        tk.Button(ctrl, text="Apply", bg=UI_BLUE, fg=UI_WHITE, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  command=self._apply_rag).pack(side="left", padx=(0, 8))
        tk.Button(ctrl, text="Detect deadlock", bg=UI_RED, fg=UI_WHITE, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  command=self._run_rag_detection).pack(side="left")

        self._info_banner(p, self.rag_info)

        cfg = tk.Frame(p, bg=UI_BG)
        cfg.pack(fill="x", pady=(0, 8))
        self.r_n_var = tk.IntVar(value=2)
        self.r_m_var = tk.IntVar(value=2)
        tk.Label(cfg, text="Processes", bg=UI_BG, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
        tk.Spinbox(cfg, from_=1, to=8, width=4, textvariable=self.r_n_var,
                   font=("Segoe UI", 10), command=self._rebuild_rag_table).pack(side="left", padx=(4, 12))
        tk.Label(cfg, text="Resources", bg=UI_BG, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
        tk.Spinbox(cfg, from_=1, to=8, width=4, textvariable=self.r_m_var,
                   font=("Segoe UI", 10), command=self._rebuild_rag_table).pack(side="left", padx=(4, 12))

        body = tk.Frame(p, bg=UI_BG)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)

        table_wrap = tk.Frame(body, bg=UI_BG)
        table_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.rag_table_frame = tk.Frame(table_wrap, bg=UI_BG)
        self.rag_table_frame.pack(fill="both", expand=True)

        chart_wrap = tk.Frame(body, bg=UI_BG2, highlightthickness=1, highlightbackground=UI_BORDER)
        chart_wrap.grid(row=0, column=1, sticky="nsew")
        self.rag_canvas = tk.Canvas(chart_wrap, bg=UI_BG2, highlightthickness=0, height=360)
        self.rag_canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self.rag_canvas.bind("<Configure>", lambda _e: self._draw_rag())

        self.rag_holder_vars: list[tk.StringVar] = []
        self.rag_wait_vars: list[tk.StringVar] = []

    def _rebuild_rag_table(self):
        for w in self.rag_table_frame.winfo_children():
            w.destroy()
        self.rag_holder_vars = []
        self.rag_wait_vars = []

        tk.Label(self.rag_table_frame, text="RESOURCE HOLDERS", bg=UI_BG, fg=UI_TEXT2,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        for r in range(self.r_m_var.get()):
            row = tk.Frame(self.rag_table_frame, bg=UI_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"R{r}", bg=UI_BG, fg=PCOLS[r % len(PCOLS)],
                     font=("Segoe UI", 10, "bold"), width=4).pack(side="left")
            var = tk.StringVar(value="—")
            self.rag_holder_vars.append(var)
            ttk.Combobox(row, textvariable=var, width=8, state="readonly",
                         values=["—"] + [f"P{p}" for p in range(self.r_n_var.get())]).pack(side="left")

        tk.Label(self.rag_table_frame, text="PROCESS WAITING FOR", bg=UI_BG, fg=UI_TEXT2,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(12, 4))
        for pidx in range(self.r_n_var.get()):
            row = tk.Frame(self.rag_table_frame, bg=UI_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"P{pidx}", bg=UI_BG, fg=PCOLS[pidx % len(PCOLS)],
                     font=("Segoe UI", 10, "bold"), width=4).pack(side="left")
            var = tk.StringVar(value="—")
            self.rag_wait_vars.append(var)
            ttk.Combobox(row, textvariable=var, width=8, state="readonly",
                         values=["—"] + [f"R{r}" for r in range(self.r_m_var.get())]).pack(side="left")

    def _load_rag_preset(self, preset: dict):
        self.r_n_var.set(preset["num_processes"])
        self.r_m_var.set(preset["num_resources"])
        self._rebuild_rag_table()
        for r, holder in enumerate(preset["holders"]):
            self.rag_holder_vars[r].set(f"P{holder}" if holder >= 0 else "—")
        for p, resource in enumerate(preset["waiting"]):
            self.rag_wait_vars[p].set(f"R{resource}" if resource >= 0 else "—")
        self._apply_rag()

    def _apply_rag(self):
        try:
            n, m = self.r_n_var.get(), self.r_m_var.get()
            if len(self.rag_holder_vars) != m or len(self.rag_wait_vars) != n:
                self._rebuild_rag_table()
            self.rag = ResourceAllocationGraph(n, m)
            for r, var in enumerate(self.rag_holder_vars):
                val = var.get()
                if val != "—":
                    self.rag.assign(r, int(val[1:]))
            for p, var in enumerate(self.rag_wait_vars):
                val = var.get()
                if val != "—":
                    self.rag.request(p, int(val[1:]))
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        self._draw_rag()
        self.rag_info.set("Graph updated. Run detection to check for a cycle.")

    def _run_rag_detection(self):
        if not self.rag:
            self._apply_rag()
        if not self.rag:
            return
        result = self.rag.detect_deadlock()
        self._draw_rag(cycle=result.steps[0]["cycle"] if result.deadlocked else None)
        if result.deadlocked:
            cycle = " → ".join(f"P{p}" for p in result.steps[0]["cycle"])
            self.rag_info.set(f"✗ Deadlock! Cycle in wait-for graph: {cycle}")
        else:
            self.rag_info.set("✓ No cycle — system is not deadlocked.")

    def _draw_rag(self, cycle: list[int] | None = None):
        c = self.rag_canvas
        c.delete("all")
        if not self.rag:
            return

        W = max(c.winfo_width(), 420)
        H = max(c.winfo_height(), 320)
        n, m = self.rag.num_processes, self.rag.num_resources

        p_pos = {i: (80, 40 + i * (H - 80) / max(n - 1, 1)) for i in range(n)}
        r_pos = {i: (W - 80, 40 + i * (H - 80) / max(m - 1, 1)) for i in range(m)}

        cycle_edges: set[tuple[int, int]] = set()
        if cycle and len(cycle) > 1:
            for i in range(len(cycle) - 1):
                cycle_edges.add((cycle[i], cycle[i + 1]))

        wfg = self.rag.build_wait_for_graph()
        for src, dst in wfg.to_edges():
            x0, y0 = p_pos[src]
            x1, y1 = p_pos[dst]
            color = UI_RED if (src, dst) in cycle_edges else UI_YELLOW
            c.create_line(x0 + 18, y0, x1 - 18, y1, fill=color, width=2, arrow=tk.LAST)
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2 - 16
            c.create_text(mx, my, text=f"P{src}→P{dst}", fill=color, font=("Segoe UI", 8))

        for r, (x, y) in r_pos.items():
            holder = self.rag.holders[r]
            c.create_rectangle(x - 16, y - 16, x + 16, y + 16, fill=UI_BG3, outline=UI_TEXT2)
            c.create_text(x, y, text=f"R{r}", fill=UI_TEXT, font=("Segoe UI", 9, "bold"))
            if holder >= 0:
                hx, hy = p_pos[holder]
                c.create_line(x - 16, y, hx + 18, hy, fill=UI_GREEN, width=2, arrow=tk.LAST)

        for p, (x, y) in p_pos.items():
            waiting = self.rag.waiting[p]
            col = PCOLS[p % len(PCOLS)]
            c.create_oval(x - 18, y - 18, x + 18, y + 18, fill=col, outline=col)
            c.create_text(x, y, text=f"P{p}", fill=UI_WHITE, font=("Segoe UI", 9, "bold"))
            if waiting >= 0:
                wx, wy = r_pos[waiting]
                c.create_line(x + 18, y, wx - 16, wy, fill=UI_ORANGE, width=2,
                              dash=(4, 3), arrow=tk.LAST)

        c.create_text(W / 2, 16, text="Processes (left) · Resources (right) · Yellow/red = wait-for edges",
                      fill=UI_TEXT3, font=("Segoe UI", 8))

    # ── Prevention tab ───────────────────────────────────────────────────────

    def _build_prevention_panel(self):
        p = self.panels["prevention"]
        self.prev_info = tk.StringVar(
            value="Request resources in increasing ID order. Lower/equal IDs are denied."
        )

        ctrl = tk.Frame(p, bg=UI_BG)
        ctrl.pack(fill="x", pady=(0, 8))
        tk.Label(ctrl, text="Processes", bg=UI_BG, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
        self.prev_n_var = tk.IntVar(value=3)
        tk.Spinbox(ctrl, from_=1, to=8, width=4, textvariable=self.prev_n_var,
                   font=("Segoe UI", 10), command=self._reset_prevention).pack(side="left", padx=(4, 12))
        tk.Button(ctrl, text="Reset", bg=UI_BG3, fg=UI_TEXT, relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  command=self._reset_prevention).pack(side="left")

        self._info_banner(p, self.prev_info)

        req = tk.Frame(p, bg=UI_BG2, highlightthickness=1, highlightbackground=UI_BORDER)
        req.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(req, bg=UI_BG2, padx=10, pady=8)
        inner.pack(fill="x")
        tk.Label(inner, text="Process", bg=UI_BG2, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
        self.prev_p_var = tk.StringVar(value="0")
        self._entry(inner, self.prev_p_var, width=4)
        tk.Label(inner, text="Resource ID", bg=UI_BG2, fg=UI_TEXT2, font=("Segoe UI", 9)).pack(side="left")
        self.prev_r_var = tk.StringVar(value="2")
        self._entry(inner, self.prev_r_var, width=4)
        tk.Button(inner, text="Request", bg=UI_GREEN, fg=UI_WHITE, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  command=self._prev_request).pack(side="left", padx=(0, 8))
        tk.Button(inner, text="Release", bg=UI_ORANGE, fg=UI_WHITE, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  command=self._prev_release).pack(side="left")

        self.prev_state_tree = self._styled_tree(
            p, ["Process", "Highest resource held"], [120, 220], height=6
        )

        log_wrap = tk.Frame(p, bg=UI_BORDER, padx=1, pady=1)
        log_wrap.pack(fill="both", expand=True, pady=(8, 0))
        self.prev_log = tk.Text(log_wrap, height=10, bg=UI_BG2, fg=UI_TEXT2,
                                insertbackground=UI_TEXT, relief="flat",
                                font=("Courier New", 10), state="disabled")
        self.prev_log.pack(fill="both", expand=True)
        self.prev_log.tag_configure("ok", foreground=UI_GREEN)
        self.prev_log.tag_configure("deny", foreground=UI_RED)

        self._reset_prevention()

    def _reset_prevention(self):
        self.prevention = DeadlockPrevention(self.prev_n_var.get())
        for row in self.prev_state_tree.get_children():
            self.prev_state_tree.delete(row)
        for p in range(self.prevention.n):
            self.prev_state_tree.insert("", "end", values=(f"P{p}", "none"))
        self.prev_log.config(state="normal")
        self.prev_log.delete("1.0", "end")
        self.prev_log.insert("end", "Prevention state reset.\n")
        self.prev_log.config(state="disabled")
        self.prev_info.set("Request resources in increasing ID order. Lower/equal IDs are denied.")

    def _refresh_prevention_table(self):
        for row in self.prev_state_tree.get_children():
            self.prev_state_tree.delete(row)
        for p in range(self.prevention.n):
            held = self.prevention.highest_resource_held[p]
            label = "none" if held < 0 else f"R{held}"
            self.prev_state_tree.insert("", "end", values=(f"P{p}", label))

    def _log_prevention(self, msg: str, ok: bool):
        self.prev_log.config(state="normal")
        tag = "ok" if ok else "deny"
        self.prev_log.insert("end", msg + "\n", tag)
        self.prev_log.see("end")
        self.prev_log.config(state="disabled")
        self.prev_info.set(msg)

    def _prev_request(self):
        try:
            pid = int(self.prev_p_var.get().strip())
            rid = int(self.prev_r_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Process and resource must be integers.")
            return
        ok, msg = self.prevention.request_resource(pid, rid)
        self._refresh_prevention_table()
        self._log_prevention(msg, ok)

    def _prev_release(self):
        try:
            pid = int(self.prev_p_var.get().strip())
            rid = int(self.prev_r_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Process and resource must be integers.")
            return
        ok, msg = self.prevention.release_resource(pid, rid)
        self._refresh_prevention_table()
        self._log_prevention(msg, ok)


# ── CLI demo / quick self-test ───────────────────────────────────────────────

def _demo() -> None:
    print("=== Banker's Algorithm (Avoidance) ===")
    banker = banker_from_preset()
    result = banker.is_safe()
    print(f"Safe: {result.safe}")
    if result.safe:
        print("Safe sequence:", " → ".join(f"P{p}" for p in result.sequence))

    req = [0, 2, 0]
    grant = banker.request_resources(1, req)
    print(f"Request {req} for P1: {grant.message}")

    print("\n=== Deadlock Detection ===")
    detector = detection_from_preset()
    det = detector.detect_deadlock()
    print(f"Deadlocked: {det.deadlocked}")
    if det.deadlocked:
        print("Deadlocked processes:", [f"P{p}" for p in det.processes])

    print("\n=== Resource Allocation Graph ===")
    rag = rag_from_preset()
    rag_det = rag.detect_deadlock()
    print(f"Deadlocked: {rag_det.deadlocked}")
    if rag_det.deadlocked:
        print("Cycle:", " → ".join(f"P{p}" for p in rag_det.steps[0]["cycle"]))

    print("\n=== Deadlock Prevention ===")
    prevention = DeadlockPrevention(2)
    ok, msg = prevention.request_resource(0, 2)
    print(msg)
    ok, msg = prevention.request_resource(0, 1)
    print(msg)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        _demo()
    else:
        DeadlockApp().mainloop()
