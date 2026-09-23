"""
NL2SQL 工具
- LLM 根据自然语言生成 SQL
- sqlparse 语法校验 + 黑名单拦截
- 仅允许 SELECT，强制 LIMIT ≤ 100
- 执行 SQLite 查询并自然语言回显
"""
import os
import re
import sqlite3
from typing import Tuple

import sqlparse
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate

from tool_registry import registry

load_dotenv()

DB_PATH = os.getenv("NL2SQL_DB_PATH", os.path.join(os.path.dirname(__file__), "ops.db"))

# 表结构（供 LLM 生成 SQL 时参考）
TABLE_SCHEMA = """
servers(id, hostname, ip, os, status, created_at)
metrics(id, server_id, cpu, memory, disk, gpu_util, gpu_mem_used_gb, gpu_mem_total_gb, ts)
alerts(id, server_id, level, message, ts)
servers.status: running/stopped
alerts.level: info/warning/critical
说明：
- 数据来源为 psutil 等真实采集（非模拟数据），metrics 每次采集追加一条快照；
- gpu_util / gpu_mem_used_gb / gpu_mem_total_gb 为显卡利用率与显存（GB），无显卡或驱动不支持时为 NULL；
- metrics 是时序表，每个 server_id 可能有多个不同 ts（采集时间）的快照；
- 查询"当前/最新/现在"性能时，只取每台服务器最新一条（按 server_id 取 MAX(ts) 对应记录），不要返回同一台服务器多条记录；
- 查询 metrics 时 SELECT 必须包含 ts 列，便于区分采集时间点；
- 仅当用户明确要"历史趋势/所有记录"时才返回同一台服务器的多条快照。
"""

# 黑名单关键词（FR-9.4 SQL 注入防护）
BLACKLIST = [
    "DROP", "DELETE", "TRUNCATE", "ALTER", "GRANT",
    "UPDATE", "REPLACE", "RENAME", "INSERT", "CREATE",
]

NL2SQL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", f"""你是一个 SQL 生成器。根据用户的自然语言问题，基于以下表结构生成一条 SQLite 查询语句。

表结构：
{TABLE_SCHEMA}

规则：
1. 只生成 SELECT 语句，不要生成任何写入/修改/删除语句；
2. 必须包含 LIMIT 子句，且 LIMIT ≤ 100；
3. 只返回 SQL 语句本身，不要解释，不要加 markdown 代码块；
4. metrics 是时序表，每个 server_id 有多条不同 ts 的快照；查询"当前/最新/现在"性能时，只取每台服务器最新一条（按 server_id 分组取 MAX(ts)），不要返回同一台服务器多条记录；
5. 查询 metrics 时 SELECT 必须包含 ts 列；仅当用户明确要"历史趋势/所有记录"时才返回同一台服务器的多条快照。"""),
    ("human", "{question}")
])


def _validate_sql(sql: str) -> Tuple[bool, str]:
    """
    SQL 安全校验：
    - sqlparse 解析成功
    - 仅 SELECT 语句
    - 无黑名单关键词
    - 强制 LIMIT ≤ 100
    返回 (是否通过, 处理后的 SQL 或错误信息)
    """
    sql = sql.strip().rstrip(";")
    if not sql:
        return False, "SQL 为空"

    # 黑名单检查（不区分大小写）
    sql_upper = sql.upper()
    for kw in BLACKLIST:
        if re.search(rf"\b{kw}\b", sql_upper):
            return False, f"SQL 包含禁止关键词: {kw}"

    # sqlparse 解析 + 语句类型校验
    parsed = sqlparse.parse(sql)
    if not parsed:
        return False, "SQL 解析失败"
    stmt = parsed[0]
    stmt_type = stmt.get_type()
    if stmt_type != "SELECT":
        return False, f"仅允许 SELECT 语句，当前为: {stmt_type}"

    # 强制 LIMIT ≤ 100
    has_limit = bool(re.search(r"\bLIMIT\b", sql_upper))
    if not has_limit:
        sql = f"{sql} LIMIT 100"
    else:
        # 提取 LIMIT 数值，超过 100 则截断
        m = re.search(r"\bLIMIT\s+(\d+)", sql_upper)
        if m:
            limit_val = int(m.group(1))
            if limit_val > 100:
                sql = re.sub(r"\bLIMIT\s+\d+", "LIMIT 100", sql, flags=re.IGNORECASE)

    return True, sql


def _format_result(rows: list, columns: list) -> str:
    """把查询结果格式化为自然语言可读文本"""
    if not rows:
        return "查询结果为空。"
    lines = [f"查询到 {len(rows)} 条记录："]
    header = " | ".join(columns)
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows[:20]:  # 最多展示 20 行
        lines.append(" | ".join(str(v) for v in row))
    if len(rows) > 20:
        lines.append(f"... 共 {len(rows)} 条，仅展示前 20 条")
    return "\n".join(lines)


def _generate_validated_sql(question: str) -> Tuple[bool, str]:
    """
    公共逻辑：LLM 生成 SQL → 去 markdown → 安全校验。
    返回 (是否通过, 校验后的 SQL 或错误信息)
    """
    llm = ChatOpenAI(
        model_name=os.getenv("SILICONFLOW_MODEL_NAME"),
        temperature=0.0,
        api_key=os.getenv("SILICONFLOW_API_KEY"),
        base_url=os.getenv("SILICONFLOW_BASE_URL"),
    )
    resp = llm.invoke(NL2SQL_PROMPT.format_messages(question=question))
    raw_sql = resp.content.strip()
    # 去除可能的 markdown 代码块
    if raw_sql.startswith("```"):
        raw_sql = raw_sql.strip("`")
        if raw_sql.lower().startswith("sql"):
            raw_sql = raw_sql[3:]
    raw_sql = raw_sql.strip()

    ok, sql_or_err = _validate_sql(raw_sql)
    if not ok:
        return False, f"SQL 安全校验未通过：{sql_or_err}\n生成的 SQL: {raw_sql}"
    return True, sql_or_err


@tool
def nl2sql_query(question: str) -> str:
    """
    将自然语言问题转为 SQL 并查询运维数据库（ops.db），返回历史/聚合数据。
    当用户想查询运维数据库中多台服务器的历史指标、告警记录或聚合统计时调用此工具。
    注意：若用户只要"当前/实时/本机"设备状态，请改用 get_server_status，不要调用本工具。

    Args:
        question: 自然语言问题，如"CPU使用率最高的服务器是哪台"、"列出所有宕机的服务器"
    """
    try:
        ok, sql_or_err = _generate_validated_sql(question)
        if not ok:
            return sql_or_err
        validated_sql = sql_or_err

        # 执行查询
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(validated_sql)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description] if cur.description else []
        conn.close()

        # 自然语言回显
        result_text = _format_result([tuple(r) for r in rows], columns)
        return f"执行 SQL: {validated_sql}\n{result_text}"

    except sqlite3.Error as e:
        return f"数据库执行失败: {e}"
    except Exception as e:
        return f"NL2SQL 处理失败: {e}"


@tool
def generate_sql(question: str) -> str:
    """
    根据自然语言描述生成 SQL 语句（不执行查询），仅返回 SQL 本身。
    当用户明确要求"写SQL"、"生成查询语句"、"给我一条SQL"、"帮我写个查询"，
    只想获得 SQL 语句而非查询结果时调用此工具。

    Args:
        question: 自然语言描述，如"写一个查询服务器CPU和内存的多表关联SQL"
    """
    try:
        ok, sql_or_err = _generate_validated_sql(question)
        if not ok:
            return sql_or_err
        return sql_or_err
    except Exception as e:
        return f"SQL 生成失败: {e}"


# 注册到工具中心
registry.register(nl2sql_query)
registry.register(generate_sql)
