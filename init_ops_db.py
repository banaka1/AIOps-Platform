"""
初始化/采集真实运维数据库（SQLite）
- servers: 本机真实信息（hostname / IP / OS 由 psutil 实时采集）
- metrics: 每运行一次追加一条真实快照（CPU / 内存 / 磁盘 / GPU），可反复运行积累历史
- alerts: 依据本次快照的真实使用率按阈值生成告警（CPU>=90 / 内存>=85 / 磁盘>=90 / GPU>=95）
- 首次运行（或检测到旧模拟库缺少 GPU 列）时自动重建全部表并清除模拟数据

运行: python init_ops_db.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
from server_status import _collect_metrics, _gpu_info  # 复用真实采集逻辑

DB_PATH = os.path.join(os.path.dirname(__file__), "ops.db")

SCHEMA = """
DROP TABLE IF EXISTS metrics;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS servers;

CREATE TABLE servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname VARCHAR(64) NOT NULL,
    ip VARCHAR(32) NOT NULL,
    os VARCHAR(32),
    status VARCHAR(16) DEFAULT 'running',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER NOT NULL,
    cpu REAL,
    memory REAL,
    disk REAL,
    gpu_util REAL,
    gpu_mem_used_gb REAL,
    gpu_mem_total_gb REAL,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (server_id) REFERENCES servers(id)
);

CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER NOT NULL,
    level VARCHAR(16),
    message TEXT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (server_id) REFERENCES servers(id)
);
"""


def _needs_rebuild(conn: sqlite3.Connection) -> bool:
    """metrics 表不存在或缺少 gpu_util 列（旧模拟库）时需要重建"""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(metrics)")}
        return not cols or "gpu_util" not in cols
    except sqlite3.Error:
        return True


def _upsert_server(conn: sqlite3.Connection, m: dict) -> int:
    """按 hostname 幂等写入本机真实信息，返回 server_id"""
    row = conn.execute(
        "SELECT id FROM servers WHERE hostname = ?", (m["hostname"],)
    ).fetchone()
    if row:
        server_id = row[0]
        conn.execute(
            "UPDATE servers SET ip = ?, os = ?, status = 'running' WHERE id = ?",
            (m["ip"], m["os"], server_id),
        )
    else:
        cur = conn.execute(
            "INSERT INTO servers (hostname, ip, os, status) VALUES (?, ?, ?, 'running')",
            (m["hostname"], m["ip"], m["os"]),
        )
        server_id = cur.lastrowid
    return server_id


def _insert_snapshot(conn: sqlite3.Connection, server_id: int, m: dict, gpu: dict) -> None:
    """写入一条真实指标快照"""
    gpu_util = gpu.get("util") if gpu else None
    gpu_mem_used = (
        round(gpu["mem_used_bytes"] / 1024 ** 3, 2)
        if gpu and gpu.get("mem_used_bytes") is not None else None
    )
    gpu_mem_total = (
        round(gpu["mem_total_bytes"] / 1024 ** 3, 2)
        if gpu and gpu.get("mem_total_bytes") else None
    )
    conn.execute(
        "INSERT INTO metrics (server_id, cpu, memory, disk, gpu_util, gpu_mem_used_gb, gpu_mem_total_gb) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (server_id, m["cpu_percent"], m["memory_percent"], m["disk_percent"],
         gpu_util, gpu_mem_used, gpu_mem_total),
    )


def _insert_alerts(conn: sqlite3.Connection, server_id: int, m: dict, gpu: dict) -> int:
    """按真实使用率与阈值生成告警，返回写入条数"""
    alerts = []
    if m["cpu_percent"] >= 90:
        alerts.append(("critical", f"CPU 使用率 {m['cpu_percent']}% 超过 90%"))
    if m["memory_percent"] >= 85:
        alerts.append(("warning", f"内存使用率 {m['memory_percent']}% 超过 85%"))
    if m["disk_percent"] >= 90:
        alerts.append(("critical", f"磁盘使用率 {m['disk_percent']}% 超过 90%"))
    if gpu and gpu.get("util") is not None and gpu["util"] >= 95:
        alerts.append(("warning", f"GPU 使用率 {gpu['util']}% 持续高位"))
    for level, message in alerts:
        conn.execute(
            "INSERT INTO alerts (server_id, level, message) VALUES (?, ?, ?)",
            (server_id, level, message),
        )
    return len(alerts)


def main():
    m = _collect_metrics()
    gpus = _gpu_info()
    gpu = gpus[0] if gpus else None

    conn = sqlite3.connect(DB_PATH)
    try:
        rebuild = _needs_rebuild(conn)
        if rebuild:
            conn.executescript(SCHEMA)
            print("检测到旧模拟库或空库，已重建表结构（清除全部模拟数据）")
        else:
            conn.commit()

        server_id = _upsert_server(conn, m)
        _insert_snapshot(conn, server_id, m, gpu)
        n_alerts = _insert_alerts(conn, server_id, m, gpu)
        conn.commit()

        servers = conn.execute("SELECT COUNT(*) FROM servers").fetchone()[0]
        metrics = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
        alerts_total = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        print(f"✅ 真实快照已写入: {DB_PATH}")
        print(f"   {m['hostname']} | CPU {m['cpu_percent']}% | 内存 {m['memory_percent']}% "
              f"| 磁盘 {m['disk_percent']}% | GPU {gpu['util'] if gpu else '无'}%")
        print(f"   本次新增告警 {n_alerts} 条 | 当前累计: servers({servers}), metrics({metrics}), alerts({alerts_total})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
