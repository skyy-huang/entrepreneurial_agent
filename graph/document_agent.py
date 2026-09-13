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
        max_retries=3,  # 增加自动重试次数，防止网络波动
        timeout=120,    # 增加超时时间
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
    prompt = f"""作为一个处理商业计划书的AI，请阅读以下项目计划书的内容，
提取其中的关键商业要素，以用于构建商业知识图谱和超图（Hypergraph）。

请严格遵守以下 JSON 格式输出，不要包含任意多余的Markdown标记或说明文字：
{{
    "nodes": [
        {{"id": "实体名称(如:Z世代/SaaS/降本增效)", "type": "实体分类(目标用户/核心痛点/解决方案/商业模式/核心技术)", "description": "具体描述"}}
    ],
    "edges": [
        {{"source": "源实体id", "target": "目标实体id", "relation": "二元关系(如:解决/依赖于)"}}
    ],
    "hyperedges": [
        {{
            "id": "超边名称(如:软硬件协同变现闭环)", 
            "nodes": ["节点id1", "节点id2", "节点id3", "节点id4"], 
            "description": "描述这些节点是如何共同协作、缺一不可地构成一个成功的商业模式或技术护城河的"
        }}
    ]
}}

项目计划书内容如下：
{text_to_summarize}
"""
    try:
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        return response.content
    except Exception as e:
        print(f"Error requesting LLM summary: {e}")
        return text[:1500]  # 若请求失败，返回原文本前1500字作为降级方案
