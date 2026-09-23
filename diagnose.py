"""
故障诊断工具（FR-9）- RAG 升级版
- 首选 Chroma 向量库做语义检索（嵌入走硅基流动 OpenAI 兼容接口）
- 向量库未初始化、检索异常或无命中时，自动降级为 JSON 关键词匹配
- 保留安全免责声明：命令仅供参考，需先在测试环境验证
"""
import os
import json
from typing import Optional

from langchain_core.tools import tool
from dotenv import load_dotenv

from tool_registry import registry

load_dotenv()
# 绝对路径定位，原始json文件记忆库
# os.path.join()能够自动补全连接符，防止手动设置系统不适配
KB_PATH = os.getenv(
    "FAULT_KB_PATH",
    os.path.join(os.path.dirname(__file__), "fault_kb.json"),
)
# chroma向量库持久化路径
CHROMA_DIR = os.getenv(
    "FAULT_CHROMA_PATH",
    os.path.join(os.path.dirname(__file__), "chroma_db"),
)
# chroma向量库集合名，一个库可以有多个集合，集合名相当于表名，隔离不同类型的向量数据
CHROMA_COLLECTION = os.getenv("FAULT_CHROMA_COLLECTION", "fault_kb")
# 向量嵌入模型，默认使用 BAAI/bge-large-zh-v1.5中文向量模型
EMBEDDING_MODEL = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
# 向量检索返回 top k 个结果，默认最相关 3 个
RETRIEVE_TOP_K = int(os.getenv("FAULT_TOP_K", "3"))

_kb_cache: Optional[dict] = None
_retriever = None


def _load_kb() -> dict:
    global _kb_cache
    if _kb_cache is None:
        with open(KB_PATH, "r", encoding="utf-8") as f:
            _kb_cache = json.load(f)
    return _kb_cache


def _get_retriever():
    """惰性初始化 Chroma 检索器；初始化失败返回 None，走关键词降级"""
    global _retriever
    if _retriever is not None:
        return _retriever
    try:
        from langchain_chroma import Chroma
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            check_embedding_ctx_length=False,
        )
        vs = Chroma(
            collection_name=CHROMA_COLLECTION,
            embedding_function=embeddings,
            persist_directory=CHROMA_DIR,
        )
        _retriever = vs.as_retriever(search_kwargs={"k": RETRIEVE_TOP_K})
    except Exception as e:
        print(f"[diagnose] Chroma 初始化失败，降级关键词匹配: {e}")
        _retriever = None
    return _retriever


def _match_fault_keyword(symptom: str) -> Optional[dict]:
    """关键词匹配兜底（与原实现一致）"""
    kb = _load_kb()
    symptom_lower = symptom.lower()
    best_match = None
    best_score = 0
    for fault in kb["faults"]:
        score = sum(1 for kw in fault["keywords"] if kw.lower() in symptom_lower)
        if score > best_score:
            best_score = score
            best_match = fault
    return best_match if best_score > 0 else None


def _match_fault_rag(symptom: str) -> Optional[dict]:
    """向量检索匹配；命中返回对应 fault dict，否则 None"""
    retriever = _get_retriever()
    if retriever is None:
        return None
    try:
        docs = retriever.invoke(symptom)
    except Exception as e:
        print(f"[diagnose] 向量检索异常，降级关键词匹配: {e}")
        return None
    if not docs:
        return None
    fault_id = docs[0].metadata.get("id")
    for fault in _load_kb()["faults"]:
        if fault["id"] == fault_id:
            return fault
    return None


def _match_fault(symptom: str) -> Optional[dict]:
    """先 RAG 语义检索，未命中或不可用则降级关键词匹配"""
    fault = _match_fault_rag(symptom)
    if fault is not None:
        return fault
    return _match_fault_keyword(symptom)


@tool
def diagnose_fault(symptom: str) -> str:
    """
    运维故障诊断。当用户描述服务器故障、性能问题、报错等需要排查的问题时调用此工具。
    返回分步骤排查清单和建议追问的问题。

    Args:
        symptom: 故障现象描述，如"CPU飙高"、"服务宕机了"、"磁盘满了"
    """
    fault = _match_fault(symptom)
    if not fault:
        return (
            "未匹配到具体故障类型。请提供更详细的故障现象，例如：\n"
            "- 是哪台服务器？\n"
            "- 具体现象是什么（CPU高/内存不足/服务宕机/网络不通/数据库慢）？\n"
            "- 问题持续多久了？\n"
            "你也可以直接描述现象，我会给出排查步骤。"
        )

    steps_text = "\n".join(fault["steps"])
    follow_up = "、".join(fault["follow_up"])
    return (
        "⚠️ 以下排查命令仅供参考，执行前请确认当前环境和权限，"
        "建议先在测试环境验证，避免在生产环境直接执行有副作用的操作。\n\n"
        f"【{fault['title']}】排查步骤：\n{steps_text}\n\n"
        f"为进一步定位，建议确认：{follow_up}"
    )


# 注册到工具中心
registry.register(diagnose_fault)
