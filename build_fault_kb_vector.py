"""
构建故障知识库的 Chroma 向量索引
- 读取 fault_kb.json
- 每条故障拼接 title/keywords/steps 作为 page_content，metadata 存 id+title
- 写入持久化 Chroma 目录（默认 ./chroma_db），collection=fault_kb
- 幂等：每次先删旧 collection 再重建，避免重复 embedding 累积
运行：python build_fault_kb_vector.py
"""
import os
import json

from dotenv import load_dotenv

load_dotenv()

KB_PATH = os.getenv(
    "FAULT_KB_PATH",
    os.path.join(os.path.dirname(__file__), "fault_kb.json"),
)
CHROMA_DIR = os.getenv(
    "FAULT_CHROMA_PATH",
    os.path.join(os.path.dirname(__file__), "chroma_db"),
)
CHROMA_COLLECTION = os.getenv("FAULT_CHROMA_COLLECTION", "fault_kb")
EMBEDDING_MODEL = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")


def build():
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings
    from langchain_core.documents import Document

    with open(KB_PATH, "r", encoding="utf-8") as f:
        kb = json.load(f)

    docs = []
    for fault in kb["faults"]:
        content = (
            f"故障：{fault['title']}\n"
            f"关键词：{', '.join(fault['keywords'])}\n"
            f"排查步骤：\n" + "\n".join(fault["steps"])
        )
        docs.append(Document(
            page_content=content,
            metadata={"id": fault["id"], "title": fault["title"]},
        ))

    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=os.getenv("SILICONFLOW_API_KEY"),
        base_url=os.getenv("SILICONFLOW_BASE_URL"),
        check_embedding_ctx_length=False,
    )

    # 幂等：先删旧 collection 再重建
    vs = Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )
    try:
        vs.delete_collection()
    except Exception:
        pass

    vs = Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )
    ids = [d.metadata["id"] for d in docs]
    vs.add_documents(docs, ids=ids)

    print(f"✅ 故障知识库向量索引已构建: {CHROMA_DIR}")
    print(f"   Collection: {CHROMA_COLLECTION}")
    print(f"   Embedding model: {EMBEDDING_MODEL}")
    print(f"   故障条目: {len(docs)} 条")


if __name__ == "__main__":
    build()
