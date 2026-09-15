"""
Agent 编排核心
- 意图识别（IntentClassifier）
- 工具注册中心（ToolRegistry）统一 bind_tools
- 多工具循环（上限 3 次）
- 从 MySQL 拉历史 → 调 LLM → 持久化 messages/tool_call_logs
"""
import os
import time
from typing import List, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from models import Message as DBMessage, ToolCallLog
from tool_registry import registry
from intent import intent_classifier
from output_validator import output_validator
import nl2sql  # noqa: F401  触发 nl2sql_query 工具注册
import diagnose  # noqa: F401  触发 diagnose_fault 工具注册

load_dotenv()

MAX_TOOL_LOOPS = 3  # FR-5.3 循环上限

# ---------------- Prompt ----------------
prompt = ChatPromptTemplate.from_messages([
    ("system", """
    你是一个智能运维助手。规则：
    1. 用户询问天气/气温/是否下雨等问题时，必须调用 get_weather 工具查询真实数据；
    2. 用户想"查看/查询"服务器/CPU/内存/磁盘/告警等运维数据时，调用 nl2sql_query 工具执行查询并返回结果；
    3. 用户明确要求"写/生成 SQL 语句"（如"写一个多表查询的SQL"）时，调用 generate_sql 工具，只返回 SQL 语句本身，不执行查询；
    4. 涉及故障排查时，调用 diagnose_fault 工具；
    5. 必须基于工具返回的真实数据回答，不要编造数值；
    6. 工具失败时如实说明，不臆造结果；
    7. 回答自然简洁，不提"工具""API"等技术词汇。
    """),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}")
])


# ---------------- 工具 ----------------
@tool
def get_weather(city: str) -> str:
    """
    查询指定城市的实时天气。
    当用户询问某地天气、气温、是否下雨、穿什么衣服等问题时调用此工具。

    Args:
        city: 中文城市名，如"北京"、"上海"、"平顶山"
    """
    api_key = os.getenv("AMAP_API_KEY")
    if not api_key:
        return "未配置AMAP_API_KEY环境变量，天气查询功能不可用！"
    weather_resp = requests.get(
        os.getenv("AMAP_WEATHER_URL"),
        params={"key": api_key, "city": city, "output": "json"},
        timeout=10
    ).json()
    if weather_resp.get("status") != "1" or not weather_resp.get("lives"):
        return "查询失败：获取天气信息失败"
    live = weather_resp["lives"][0]
    return (
        f"{live['city']} {live['reporttime']} - "
        f"温度{live['temperature']}℃，{live['weather']}，"
        f"湿度{live['humidity']}%，{live['winddirection']}风{live['windpower']}级"
    )


# 注册工具到中心（M6/M8 的工具在各自模块注册）
registry.register(get_weather)


# ---------------- 历史加载 ----------------
def load_chat_history(db: Session, session_id: str, limit: int = 20) -> List[BaseMessage]:
    rows = (
        db.query(DBMessage)
        .filter(DBMessage.session_id == session_id, DBMessage.role.in_(["human", "ai"]))
        .order_by(DBMessage.id.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    history: List[BaseMessage] = []
    for row in rows:
        if row.role == "human":
            history.append(HumanMessage(content=row.content))
        elif row.role == "ai":
            history.append(AIMessage(content=row.content))
    return history


# ---------------- 持久化辅助 ----------------
def _save_message(db: Session, session_id: str, role: str, content: str, tool_calls=None):
    msg = DBMessage(session_id=session_id, role=role, content=content, tool_calls=tool_calls)
    db.add(msg)
    db.flush()
    return msg


def _save_tool_log(db: Session, session_id: str, tool_name: str, args: dict, result: str, latency_ms: int):
    log = ToolCallLog(
        session_id=session_id, tool_name=tool_name, args=args,
        result=result, latency_ms=latency_ms,
    )
    db.add(log)


# ---------------- 主流程 ----------------
def test_chat_openai(message: str, session_id: str, db: Session) -> Tuple[str, str, list]:
    """
    单轮对话：意图识别 → 拉历史 → LLM 多工具循环 → 持久化
    返回 (reply, intent, tools)
    """
    # FR-4 意图识别
    intent, _confidence = intent_classifier.classify(message)

    model = ChatOpenAI(
        model_name=os.getenv("SILICONFLOW_MODEL_NAME"),
        temperature=0.7,
        api_key=os.getenv("SILICONFLOW_API_KEY"),
        base_url=os.getenv("SILICONFLOW_BASE_URL"),
    )
    # FR-5.2 一次性绑定全部工具
    model_with_tools = model.bind_tools(registry.all_tools())

    chat_history = load_chat_history(db, session_id)
    messages = prompt.format_messages(chat_history=chat_history, input=message)

    # 先存 human 消息
    _save_message(db, session_id, "human", message)

    tool_infos = []
    answer = ""

    # FR-5.3 多工具循环，上限 MAX_TOOL_LOOPS 次
    for loop in range(MAX_TOOL_LOOPS):
        response = model_with_tools.invoke(messages)

        if not response.tool_calls:
            # 无工具调用，作为最终回答候选
            answer = response.content
            break

        # 有工具调用：若模型附带了正文则落库，否则仅保留在内存上下文（避免历史出现空气泡）
        if response.content and response.content.strip():
            _save_message(
                db, session_id, "ai", response.content,
                tool_calls=response.tool_calls,
            )
        messages.append(response)

        # FR-5.4 执行所有工具调用，写 tool_call_logs
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            t0 = time.time()
            tool_obj = registry.get(tool_name)
            if tool_obj:
                tool_result = tool_obj.invoke(tool_args)
            else:
                tool_result = f"未知工具：{tool_name}"
            latency_ms = int((time.time() - t0) * 1000)

            _save_message(db, session_id, "tool", tool_result)
            _save_tool_log(db, session_id, tool_name, tool_args, tool_result, latency_ms)
            tool_infos.append({
                "name": tool_name, "args": tool_args,
                "result": tool_result, "ms": latency_ms,
            })
            messages.append(ToolMessage(content=tool_result, tool_call_id=tool_id))

        # 最后一轮循环后，再调一次 LLM 生成最终回答
        if loop == MAX_TOOL_LOOPS - 1:
            final_response = model_with_tools.invoke(messages)
            answer = final_response.content

    # FR-6 反幻觉校验：数值来源回溯，不通过重试 1 次
    tool_results = [t["result"] for t in tool_infos]
    is_valid, reason = output_validator.validate(answer or "", tool_results)
    if not is_valid:
        # 重试：追加约束提示后再调一次 LLM
        messages.append(AIMessage(content=answer or ""))
        messages.append(HumanMessage(
            content=f"你的回答存在问题：{reason}。请严格基于上方工具返回的真实数据重新回答，"
                    f"不要编造任何数值，工具失败则如实说明。"
        ))
        retry_response = model_with_tools.invoke(messages)
        answer = retry_response.content

    # 兜底：LLM 返回空内容时给默认回复，避免前端显示空白
    if not answer or not answer.strip():
        answer = "抱歉，我暂时无法生成有效回复，请稍后重试或换个问法。"

    # 持久化最终 ai 回答
    _save_message(db, session_id, "ai", answer)

    db.commit()
    return answer, intent, tool_infos


def test_chat_openai_stream(message: str, session_id: str, db: Session):
    """
    流式版单轮对话，生成器依次产出 (event, data)：
    meta / tool_call / tool_result / token / reset / done
    """
    intent, _confidence = intent_classifier.classify(message)
    yield "meta", {"intent": intent}

    model = ChatOpenAI(
        model_name=os.getenv("SILICONFLOW_MODEL_NAME"),
        temperature=0.7,
        api_key=os.getenv("SILICONFLOW_API_KEY"),
        base_url=os.getenv("SILICONFLOW_BASE_URL"),
    )
    model_with_tools = model.bind_tools(registry.all_tools())

    chat_history = load_chat_history(db, session_id)
    messages = prompt.format_messages(chat_history=chat_history, input=message)

    _save_message(db, session_id, "human", message)

    tool_infos = []
    answer = ""

    def _stream_round(msgs):
        """流式执行一轮：逐 token 产出 token 事件，返回累积后的完整 chunk"""
        full = None
        tool_detected = False
        for chunk in model_with_tools.stream(msgs):
            full = chunk if full is None else full + chunk
            if getattr(chunk, "tool_call_chunks", None):
                tool_detected = True
            elif chunk.content and not tool_detected:
                yield "token", {"text": chunk.content}
        return full

    for loop in range(MAX_TOOL_LOOPS):
        full = yield from _stream_round(messages)

        if full is None or not full.tool_calls:
            answer = (full.content or "") if full is not None else ""
            break

        # 工具决策轮：仅当模型附带了正文才落库，否则只保留在内存上下文
        if full.content and full.content.strip():
            _save_message(db, session_id, "ai", full.content, tool_calls=full.tool_calls)
        messages.append(full)

        for tool_call in full.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            yield "tool_call", {"name": tool_name, "args": tool_args}

            t0 = time.time()
            tool_obj = registry.get(tool_name)
            tool_result = tool_obj.invoke(tool_args) if tool_obj else f"未知工具：{tool_name}"
            latency_ms = int((time.time() - t0) * 1000)

            _save_message(db, session_id, "tool", tool_result)
            _save_tool_log(db, session_id, tool_name, tool_args, tool_result, latency_ms)
            tool_infos.append({
                "name": tool_name, "args": tool_args,
                "result": tool_result, "ms": latency_ms,
            })
            messages.append(ToolMessage(content=tool_result, tool_call_id=tool_id))

            yield "tool_result", {"name": tool_name, "result": tool_result, "ms": latency_ms}
    else:
        # 循环耗尽仍未得到最终回答，再流式生成一轮
        full = yield from _stream_round(messages)
        answer = (full.content or "") if full is not None else ""

    # FR-6 反幻觉校验：不通过则 reset 气泡，重试一次（同样流式）
    tool_results = [t["result"] for t in tool_infos]
    is_valid, reason = output_validator.validate(answer, tool_results)
    if not is_valid:
        bad_answer = answer
        yield "reset", {}
        answer = ""
        messages.append(AIMessage(content=bad_answer or ""))
        messages.append(HumanMessage(
            content=f"你的回答存在问题：{reason}。请严格基于上方工具返回的真实数据重新回答，"
                    f"不要编造任何数值，工具失败则如实说明。"
        ))
        full = yield from _stream_round(messages)
        answer = (full.content or "") if full is not None else ""

    if not answer or not answer.strip():
        answer = "抱歉，我暂时无法生成有效回复，请稍后重试或换个问法。"
        yield "reset", {}
        yield "token", {"text": answer}

    _save_message(db, session_id, "ai", answer)
    db.commit()
    yield "done", {"reply": answer, "tools": tool_infos}
