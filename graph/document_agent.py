import io
import os
import PyPDF2
import docx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

def _get_llm(temperature: float = 0.3) -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        temperature=temperature,
    )

async def parse_and_summarize_document(file_bytes: bytes, filename: str) -> str:
    ext = filename.split('.')[-1].lower()
    text = ""
    try:
        if ext == 'pdf':
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        elif ext in ['doc', 'docx']:
            doc = docx.Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif ext == 'txt':
            text = file_bytes.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error parsing document: {e}")
        return ""

    text = text.strip()
    if not text:
        return ""

    # 限制分析的原文长度，避免撑爆上下文（例如15000字截断）
    text_to_summarize = text[:15000]

    llm = _get_llm(temperature=0.1)
    prompt = f"""作为一个专门处理商业计划书的AI，请阅读以下项目计划书的内容，
提取其中的关键商业要素，包括但不限于：目标用户群体、核心痛点、所提供的解决方案、产品或服务的形态、商业模式及变现手段等。
请只做客观的摘要梳理，不要加入对商业计划的主观评价，保留原文中的具体例子和数据。

项目计划书内容如下：
{text_to_summarize}
"""
    try:
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        return response.content
    except Exception as e:
        print(f"Error requesting LLM summary: {e}")
        return text[:1500]  # 若请求失败，返回原文本前1500字作为降级方案
