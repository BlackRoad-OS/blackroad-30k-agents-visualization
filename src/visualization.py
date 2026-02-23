#!/usr/bin/env python3
"""
BlackRoad 30K Agents Visualization — Fleet dashboard data engine.
Generates node stats, distribution charts, capacity metrics and live
agent states suitable for rendering in any dashboard.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sqlite3
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── ANSI ──────────────────────────────────────────────────────────────────────
R  = "\033[0;31m";  G  = "\033[0;32m";  Y  = "\033[1;33m"
C  = "\033[0;36m";  B  = "\033[0;34m";  M  = "\033[0;35m"
W  = "\033[1;37m";  DIM = "\033[2m";    NC = "\033[0m";  BOLD = "\033[1m"

DB_PATH = Path(os.environ.get("VIZ_DB", Path.home() / ".blackroad" / "visualization.db"))

TOTAL_AGENTS = 30_000
NODE_NAMES   = ["octavia-pi", "lucidia-pi", "shellfish-droplet", "alice-cloud", "prism-edge"]
AGENT_TYPES  = ["worker", "reasoning", "security", "analytics", "memory", "creative"]

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class NodeStats:
    node_id: str
    hostname: str
    ip: str
    role: str          # PRIMARY | SECONDARY | EDGE | FAILOVER
    capacity: int
    active_agents: int
    idle_agents: int
    busy_agents: int
    offline_agents: int
    cpu_pct: float
    mem_pct: float
    net_mbps: float
    recorded_at: str

    def utilisation_pct(self) -> float:
        if self.capacity == 0:
            return 0.0
        return round((self.active_agents + self.busy_agents) / self.capacity * 100, 2)

    def health(self) -> str:
        u = self.utilisation_pct()
        if u > 95 or self.cpu_pct > 90:
            return "critical"
        if u > 80 or self.cpu_pct > 75:
            return "degraded"
        return "healthy"


@dataclass
class DistributionBucket:
    bucket_id: str
    dimension: str     # type | status | node | priority
    label: str
    count: int
    pct: float
    colour: str
    recorded_at: str


@dataclass
class CapacityMetric:
    metric_id: str
    node_id: str
    total_capacity: int
    used_capacity: int
    reserved_capacity: int
    free_capacity: int
    overcommit_ratio: float
    recorded_at: str

    def fill_pct(self) -> float:
        if self.total_capacity == 0:
            return 0.0
        return round(self.used_capacity / self.total_capacity * 100, 2)


@dataclass
class LiveAgentState:
    state_id: str
    agent_id: str
    agent_type: str
    status: str        # online | idle | busy | offline | error
    node_id: str
    task_count: int
    error_count: int
    last_heartbeat: str
    latency_ms: float

    def is_stale(self, threshold_seconds: int = 300) -> bool:
        try:
            ts = datetime.fromisoformat(self.last_heartbeat)
            return (datetime.utcnow() - ts).total_seconds() > threshold_seconds
        except Exception:
            return True


@dataclass
class ChartData:
    chart_id: str
    chart_type: str    # bar | pie | line | heatmap
    title: str
    labels: str        # JSON array
    datasets: str      # JSON array of {label, data, colour}
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "chart_id": self.chart_id,
            "chart_type": self.chart_type,
            "title": self.title,
            "labels": json.loads(self.labels),
            "datasets": json.loads(self.datasets),
            "generated_at": self.generated_at,
        }

# ── Database ──────────────────────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS node_stats (
        node_id         TEXT NOT NULL,
        hostname        TEXT NOT NULL,
        ip              TEXT NOT NULL,
        role            TEXT NOT NULL,
        capacity        INTEGER NOT NULL DEFAULT 0,
        active_agents   INTEGER NOT NULL DEFAULT 0,
        idle_agents     INTEGER NOT NULL DEFAULT 0,
        busy_agents     INTEGER NOT NULL DEFAULT 0,
        offline_agents  INTEGER NOT NULL DEFAULT 0,
        cpu_pct         REAL NOT NULL DEFAULT 0,
        mem_pct         REAL NOT NULL DEFAULT 0,
        net_mbps        REAL NOT NULL DEFAULT 0,
        recorded_at     TEXT NOT NULL,
        PRIMARY KEY (node_id, recorded_at)
    );

    CREATE TABLE IF NOT EXISTS distribution_buckets (
        bucket_id   TEXT PRIMARY KEY,
        dimension   TEXT NOT NULL,
        label       TEXT NOT NULL,
        count       INTEGER NOT NULL DEFAULT 0,
        pct         REAL NOT NULL DEFAULT 0,
        colour      TEXT NOT NULL DEFAULT '#888888',
        recorded_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS capacity_metrics (
        metric_id         TEXT PRIMARY KEY,
        node_id           TEXT NOT NULL,
        total_capacity    INTEGER NOT NULL,
        used_capacity     INTEGER NOT NULL,
        reserved_capacity INTEGER NOT NULL,
        free_capacity     INTEGER NOT NULL,
        overcommit_ratio  REAL NOT NULL DEFAULT 1.0,
        recorded_at       TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS live_agent_states (
        state_id       TEXT PRIMARY KEY,
        agent_id       TEXT NOT NULL,
        agent_type     TEXT NOT NULL,
        status         TEXT NOT NULL,
        node_id        TEXT NOT NULL,
        task_count     INTEGER NOT NULL DEFAULT 0,
        error_count    INTEGER NOT NULL DEFAULT 0,
        last_heartbeat TEXT NOT NULL,
        latency_ms     REAL NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS chart_data (
        chart_id     TEXT PRIMARY KEY,
        chart_type   TEXT NOT NULL,
        title        TEXT NOT NULL,
        labels       TEXT NOT NULL DEFAULT '[]',
        datasets     TEXT NOT NULL DEFAULT '[]',
        generated_at TEXT NOT NULL
    );
    """)
    conn.commit()


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _uid(p: str = "") -> str:
    import hashlib
    return p + hashlib.sha1(f"{p}{time.time_ns()}{random.random()}".encode()).hexdigest()[:10]

# ── Seed / Simulate ───────────────────────────────────────────────────────────

NODE_CONFIG = [
    ("octavia-pi",       "192.168.4.38", "PRIMARY",   22_500),
    ("lucidia-pi",       "192.168.4.64", "SECONDARY",  7_500),
    ("shellfish-droplet","159.65.43.12", "FAILOVER",      0),
    ("alice-cloud",      "10.0.0.5",     "EDGE",          0),
    ("prism-edge",       "10.0.0.6",     "EDGE",          0),
]

TYPE_COLOURS = {
    "worker":    "#4CAF50",
    "reasoning": "#2196F3",
    "security":  "#F44336",
    "analytics": "#FF9800",
    "memory":    "#9C27B0",
    "creative":  "#00BCD4",
}

TYPE_DIST = {
    "worker":    0.28,
    "reasoning": 0.14,
    "security":  0.08,
    "analytics": 0.22,
    "memory":    0.18,
    "creative":  0.10,
}


def seed_simulation(conn: sqlite3.Connection) -> None:
    """Seed realistic 30K agent simulation data."""
    now = _now()
    existing = conn.execute("SELECT COUNT(*) FROM node_stats").fetchone()[0]
    if existing > 0:
        return

    # Node stats
    for hostname, ip, role, cap in NODE_CONFIG:
        actual = cap if cap > 0 else random.randint(0, 200)
        active   = int(actual * random.uniform(0.3, 0.7))
        idle     = int(actual * random.uniform(0.1, 0.3))
        busy     = int(actual * random.uniform(0.1, 0.4))
        offline  = max(0, actual - active - idle - busy)
        conn.execute("""INSERT INTO node_stats VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (hostname, hostname, ip, role, cap,
                      active, idle, busy, offline,
                      round(random.uniform(20, 85), 1),
                      round(random.uniform(30, 90), 1),
                      round(random.uniform(10, 500), 1),
                      now))

    # Distribution by type
    for atype, frac in TYPE_DIST.items():
        count = int(TOTAL_AGENTS * frac)
        pct   = round(frac * 100, 2)
        conn.execute("INSERT INTO distribution_buckets VALUES (?,?,?,?,?,?,?)",
                     (_uid("db"), "type", atype, count, pct,
                      TYPE_COLOURS.get(atype, "#888"), now))

    # Distribution by status
    status_dist = {"online": 0.35, "idle": 0.25, "busy": 0.30, "offline": 0.07, "error": 0.03}
    status_colours = {"online":"#4CAF50","idle":"#2196F3","busy":"#FF9800","offline":"#9E9E9E","error":"#F44336"}
    for st, frac in status_dist.items():
        count = int(TOTAL_AGENTS * frac)
        conn.execute("INSERT INTO distribution_buckets VALUES (?,?,?,?,?,?,?)",
                     (_uid("db"), "status", st, count, round(frac*100, 2),
                      status_colours[st], now))

    # Capacity metrics per node
    for hostname, ip, role, cap in NODE_CONFIG:
        used     = int(cap * random.uniform(0.4, 0.8))
        reserved = int(cap * 0.1)
        free     = max(0, cap - used - reserved)
        ratio    = round(used / max(cap, 1), 3)
        conn.execute("INSERT INTO capacity_metrics VALUES (?,?,?,?,?,?,?,?)",
                     (_uid("cm"), hostname, cap, used, reserved, free, ratio, now))

    # Sample live agent states (100 representative)
    for i in range(100):
        atype  = random.choices(list(TYPE_DIST.keys()), weights=list(TYPE_DIST.values()))[0]
        status = random.choices(list(status_dist.keys()), weights=list(status_dist.values()))[0]
        node   = random.choice([n[0] for n in NODE_CONFIG[:2]])
        hb     = (datetime.utcnow() - timedelta(seconds=random.randint(0, 600))).isoformat(timespec="seconds")
        conn.execute("INSERT INTO live_agent_states VALUES (?,?,?,?,?,?,?,?,?)",
                     (_uid("ls"), f"agent-{i:05d}", atype, status, node,
                      random.randint(0, 50), random.randint(0, 5), hb,
                      round(random.uniform(1, 200), 2)))

    conn.commit()

# ── Core operations ───────────────────────────────────────────────────────────

def get_node_stats(conn: sqlite3.Connection) -> list[NodeStats]:
    rows = conn.execute("""
        SELECT * FROM node_stats WHERE recorded_at = (SELECT MAX(recorded_at) FROM node_stats)
        ORDER BY capacity DESC
    """).fetchall()
    return [NodeStats(**dict(r)) for r in rows]


def get_distribution(conn: sqlite3.Connection, dimension: str = "type") -> list[DistributionBucket]:
    rows = conn.execute("""
        SELECT * FROM distribution_buckets
        WHERE dimension=? AND recorded_at=(SELECT MAX(recorded_at) FROM distribution_buckets)
        ORDER BY count DESC
    """, (dimension,)).fetchall()
    return [DistributionBucket(**dict(r)) for r in rows]


def get_capacity_metrics(conn: sqlite3.Connection) -> list[CapacityMetric]:
    rows = conn.execute("""
        SELECT * FROM capacity_metrics
        WHERE recorded_at=(SELECT MAX(recorded_at) FROM capacity_metrics)
        ORDER BY total_capacity DESC
    """).fetchall()
    return [CapacityMetric(**dict(r)) for r in rows]


def get_live_states(conn: sqlite3.Connection, status_filter: Optional[str] = None,
                    node_filter: Optional[str] = None, limit: int = 50) -> list[LiveAgentState]:
    q = "SELECT * FROM live_agent_states WHERE 1=1"
    params: list = []
    if status_filter:
        q += " AND status=?"; params.append(status_filter)
    if node_filter:
        q += " AND node_id=?"; params.append(node_filter)
    q += " ORDER BY last_heartbeat DESC LIMIT ?"; params.append(limit)
    rows = conn.execute(q, params).fetchall()
    return [LiveAgentState(**dict(r)) for r in rows]


def generate_chart_data(conn: sqlite3.Connection, chart_type: str) -> ChartData:
    """Build chart-ready JSON payload for the given chart type."""
    now = _now()
    cid = _uid("ch")
    if chart_type == "type_distribution":
        buckets = get_distribution(conn, "type")
        labels   = json.dumps([b.label for b in buckets])
        datasets = json.dumps([{
            "label": "Agent Count",
            "data": [b.count for b in buckets],
            "colours": [b.colour for b in buckets],
        }])
        title = "Agent Distribution by Type"
    elif chart_type == "node_capacity":
        metrics = get_capacity_metrics(conn)
        labels   = json.dumps([m.node_id for m in metrics])
        datasets = json.dumps([
            {"label": "Used",     "data": [m.used_capacity     for m in metrics], "colour": "#F44336"},
            {"label": "Reserved", "data": [m.reserved_capacity for m in metrics], "colour": "#FF9800"},
            {"label": "Free",     "data": [m.free_capacity     for m in metrics], "colour": "#4CAF50"},
        ])
        title = "Node Capacity Breakdown"
    elif chart_type == "status_distribution":
        buckets  = get_distribution(conn, "status")
        labels   = json.dumps([b.label for b in buckets])
        datasets = json.dumps([{
            "label": "Agents",
            "data":    [b.count  for b in buckets],
            "colours": [b.colour for b in buckets],
        }])
        title = "Agent Status Distribution"
    else:
        raise ValueError(f"Unknown chart type: {chart_type}")

    ch = ChartData(chart_id=cid, chart_type=chart_type, title=title,
                   labels=labels, datasets=datasets, generated_at=now)
    conn.execute("INSERT INTO chart_data VALUES (?,?,?,?,?,?)",
                 (ch.chart_id, ch.chart_type, ch.title, ch.labels, ch.datasets, ch.generated_at))
    conn.commit()
    return ch


def snapshot(conn: sqlite3.Connection) -> dict:
    """Aggregate snapshot suitable for dashboard rendering."""
    nodes   = get_node_stats(conn)
    status  = get_distribution(conn, "status")
    types   = get_distribution(conn, "type")
    metrics = get_capacity_metrics(conn)
    live    = get_live_states(conn, limit=20)
    total_cap  = sum(m.total_capacity for m in metrics)
    total_used = sum(m.used_capacity  for m in metrics)
    return {
        "total_agents":   TOTAL_AGENTS,
        "total_capacity": total_cap,
        "used_capacity":  total_used,
        "fill_pct":       round(total_used / max(total_cap, 1) * 100, 2),
        "nodes":          [asdict(n) for n in nodes],
        "by_status":      [asdict(b) for b in status],
        "by_type":        [asdict(b) for b in types],
        "sample_live":    [asdict(s) for s in live],
    }

# ── Rendering helpers ─────────────────────────────────────────────────────────

HEALTH_COL = {"healthy": G, "degraded": Y, "critical": R}


def _bar(value: float, max_val: float = 100.0, width: int = 20) -> str:
    filled = int(width * min(value / max(max_val, 1), 1.0))
    col = G if value < 70 else Y if value < 90 else R
    return f"{col}{'█' * filled}{'░' * (width - filled)}{NC} {value:.1f}%"


def _header(title: str) -> None:
    print(f"\n{B}{'─' * 62}{NC}")
    print(f"{W}{BOLD}  {title}{NC}")
    print(f"{B}{'─' * 62}{NC}")

# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_stats(args: argparse.Namespace) -> None:
    conn = get_conn(); seed_simulation(conn)
    nodes = get_node_stats(conn)
    _header(f"Node Stats  [{len(nodes)} nodes]")
    for n in nodes:
        hcol = HEALTH_COL.get(n.health(), NC)
        print(f"  {W}{n.hostname:<22}{NC}  {hcol}{n.health():<10}{NC}")
        print(f"    Capacity   : {n.capacity:>6}  Utilisation: {_bar(n.utilisation_pct())}")
        print(f"    CPU        : {_bar(n.cpu_pct)}   MEM: {_bar(n.mem_pct)}")
        print(f"    Net        : {C}{n.net_mbps:.1f} Mbps{NC}   Role: {DIM}{n.role}{NC}")
        print()


def cmd_distribution(args: argparse.Namespace) -> None:
    conn = get_conn(); seed_simulation(conn)
    dim = args.dimension or "type"
    buckets = get_distribution(conn, dim)
    _header(f"Distribution by {dim.upper()}  [total {TOTAL_AGENTS:,}]")
    for b in buckets:
        bar_w = int(40 * b.pct / 100)
        print(f"  {b.label:<14}  {'█' * bar_w:<40}  {Y}{b.count:>6,}{NC}  ({b.pct:.1f}%)")
    print()


def cmd_capacity(args: argparse.Namespace) -> None:
    conn = get_conn(); seed_simulation(conn)
    metrics = get_capacity_metrics(conn)
    _header("Capacity Metrics")
    print(f"  {DIM}{'Node':<25} {'Total':>7} {'Used':>7} {'Free':>7} {'Fill%':>7}{NC}")
    print(f"  {'─'*55}")
    for m in metrics:
        fcol = G if m.fill_pct() < 70 else Y if m.fill_pct() < 90 else R
        print(f"  {m.node_id:<25} {m.total_capacity:>7,} {m.used_capacity:>7,} "
              f"{m.free_capacity:>7,} {fcol}{m.fill_pct():>6.1f}%{NC}")
    print()


def cmd_live(args: argparse.Namespace) -> None:
    conn = get_conn(); seed_simulation(conn)
    states = get_live_states(conn, status_filter=args.status,
                             node_filter=args.node, limit=args.limit)
    _header(f"Live Agent States  [{len(states)} shown]")
    STATUS_COL = {"online":G,"idle":C,"busy":Y,"offline":DIM,"error":R}
    for s in states:
        sc  = STATUS_COL.get(s.status, NC)
        stale = f" {Y}[STALE]{NC}" if s.is_stale() else ""
        print(f"  {s.agent_id:<14}  {sc}{s.status:<8}{NC}  {s.agent_type:<12}  "
              f"{DIM}{s.node_id:<22}{NC}  {s.latency_ms:>6.1f}ms{stale}")
    print()


def cmd_chart(args: argparse.Namespace) -> None:
    conn = get_conn(); seed_simulation(conn)
    chart = generate_chart_data(conn, args.chart_type)
    _header(f"Chart — {chart.title}")
    d = chart.to_dict()
    print(json.dumps(d, indent=2))
    print()


def cmd_export(args: argparse.Namespace) -> None:
    conn = get_conn(); seed_simulation(conn)
    data = snapshot(conn)
    out  = json.dumps(data, indent=2)
    if args.output:
        Path(args.output).write_text(out)
        print(f"{G}✓ Exported to {args.output}{NC}")
    else:
        print(out)


# ── Parser ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="visualization",
                                description=f"{W}BlackRoad 30K Agent Visualization Engine{NC}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("stats",        help="Show per-node statistics").set_defaults(func=cmd_stats)

    p_dist = sub.add_parser("distribution", help="Show agent distribution")
    p_dist.add_argument("--dimension", choices=["type","status","node"], default="type")
    p_dist.set_defaults(func=cmd_distribution)

    sub.add_parser("capacity",     help="Show capacity metrics").set_defaults(func=cmd_capacity)

    p_live = sub.add_parser("live", help="Show live agent states")
    p_live.add_argument("--status")
    p_live.add_argument("--node")
    p_live.add_argument("--limit", type=int, default=30)
    p_live.set_defaults(func=cmd_live)

    p_chart = sub.add_parser("chart", help="Generate chart data JSON")
    p_chart.add_argument("chart_type",
                         choices=["type_distribution","node_capacity","status_distribution"])
    p_chart.set_defaults(func=cmd_chart)

    p_export = sub.add_parser("export", help="Export full dashboard snapshot")
    p_export.add_argument("--output", "-o")
    p_export.set_defaults(func=cmd_export)

    return p


def main() -> None:
    build_parser().parse_args().__dict__.pop("func")(build_parser().parse_args())


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
