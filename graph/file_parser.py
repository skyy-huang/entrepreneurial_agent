"""
文件解析 Agent
支持解析 PDF 和 Word（.docx）格式的项目计划书，
将原始文本传给 LLM 进行结构化摘要，然后作为学生输入注入到对话流水线。
"""
import io
import os
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Maximum characters of document text fed to the LLM
_MAX_DOCUMENT_CHARS = 12_000

# ─────────────────────────────────────────────────────────────
# 文本提取（纯文本，无 LLM）
# ─────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """从 PDF 字节流中提取纯文本，合并所有页面"""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """从 DOCX 字节流中提取纯文本，保留段落结构"""
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_text(file_bytes: bytes, filename: str) -> str:
    """根据文件名后缀选择对应的提取方式，返回原始文本"""
    name = filename.lower()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    if name.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    raise ValueError(f"不支持的文件类型：{filename}（仅支持 .pdf / .docx）")


# ─────────────────────────────────────────────────────────────
# LLM 摘要（将长文档压缩成结构化简报，注入对话流水线）
# ─────────────────────────────────────────────────────────────

_FILE_SUMMARY_SYSTEM = """你是一个创业项目计划书阅读助手。
学生上传了一份项目计划书，请从中提取关键信息，输出一段**简洁、结构清晰**的中文摘要，供后续教练 Agent 使用。

摘要必须涵盖（如有）：
1. 项目名称与核心问题/痛点
2. 目标用户群体
3. 解决方案与价值主张
4. 商业模式（如何盈利）
5. 市场规模估算
6. 团队背景
7. 当前进展（idea / 原型 / MVP / 已有收入）
8. 竞争分析
9. 核心假设或风险点

如果原文缺少某项，请注明"未提及"。
摘要用中文，字数控制在 600 字以内，使用"一、二、三…"编号条目格式。"""


def _get_llm(temperature: float = 0.1) -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        temperature=temperature,
    )


async def summarize_document(raw_text: str, filename: str) -> str:
    """调用 LLM 将原始文档文本压缩为结构化摘要字符串"""
    # Prevent excessively long documents from exceeding LLM context
    truncated = raw_text[:_MAX_DOCUMENT_CHARS]
    if len(raw_text) > _MAX_DOCUMENT_CHARS:
        truncated += f"\n\n（……文档过长，仅分析前 {_MAX_DOCUMENT_CHARS} 字）"

    llm = _get_llm()
    messages = [
        SystemMessage(content=_FILE_SUMMARY_SYSTEM),
        HumanMessage(content=f"文件名：{filename}\n\n文档内容：\n{truncated}"),
    ]
    response = await llm.ainvoke(messages)
    return response.content.strip()


async def parse_and_summarize(file_bytes: bytes, filename: str) -> dict:
    """
    完整流程：
      1. 按文件类型提取纯文本
      2. 用 LLM 压缩为结构化摘要
    返回 {"raw_text": ..., "summary": ...}
    """
    raw_text = extract_text(file_bytes, filename)
    if not raw_text.strip():
        raise ValueError("文件内容为空，无法解析")

    summary = await summarize_document(raw_text, filename)
    return {
        "raw_text": raw_text,
        "summary": summary,
    }
