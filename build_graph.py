import os
import asyncio
import json
import re
from dotenv import load_dotenv
from graph.document_agent import parse_and_summarize_document

# 加载环境变量
load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "cases")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "data", "master_graph.json")

async def process_cases():
    if not os.path.exists(DATA_DIR):
        print(f"未找到数据目录: {DATA_DIR}")
        return

    master_graph = {"nodes": [], "edges": [], "hyperedges": []}
    processed_files = set()
    
    # 确保保存输出的稳定目录存在
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # 如果已存在 master_graph.json，先加载以便判断哪些文件已经处理过，并在原基础上追加
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if isinstance(existing_data, dict):
                    master_graph["nodes"] = existing_data.get("nodes", [])
                    master_graph["edges"] = existing_data.get("edges", [])
                    master_graph["hyperedges"] = existing_data.get("hyperedges", [])
                    
                    # 收集已处理过的文件名
                    for node in master_graph["nodes"]:
                        if "source_file" in node:
                            processed_files.add(node["source_file"])
                    print(f"已加载现有图谱数据，包含 {len(processed_files)} 个已经处理的文件。")
        except json.JSONDecodeError:
            print("现有 master_graph.json 损坏或格式错误，将重新生成...")
        except Exception as e:
            print(f"加载现有 master_graph.json 时发生错误: {e}")

    for filename in os.listdir(DATA_DIR):
        ext = filename.split('.')[-1].lower()
        if ext not in ['pdf', 'doc', 'docx', 'txt']:
            continue
            
        if filename in processed_files:
            print(f"跳过已处理的文件: {filename}")
            continue
            
        file_path = os.path.join(DATA_DIR, filename)
        print(f"正在处理: {filename} ...")
        
        try:
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
                
            json_str = await parse_and_summarize_document(file_bytes, filename)
            
            # 使用正则表达式提取大括号包裹的纯JSON部分，避免Markdown和外围文本干扰
            match = re.search(r'\{.*\}', json_str, re.DOTALL)
            if match:
                json_str = match.group(0)
            
            try:
                graph_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"解析 {filename} 的 JSON 数据失败: {e}\n模型原始内容:\n{json_str[:200]}...")
                continue
            
            # 为节点和边打上来源标签，便于追溯
            for node in graph_data.get("nodes", []):
                node["source_file"] = filename
                master_graph["nodes"].append(node)
                
            for edge in graph_data.get("edges", []):
                edge["source_file"] = filename
                master_graph["edges"].append(edge)
                
            for hedge in graph_data.get("hyperedges", []):
                hedge["source_file"] = filename
                master_graph["hyperedges"].append(hedge)
                
            print(f"成功提取 {filename} : {len(graph_data.get('nodes', []))} 个节点, {len(graph_data.get('hyperedges', []))} 条超边.")
            
        except json.JSONDecodeError:
            print(f"解析 {filename} 的 JSON 数据失败，LLM 输出格式错误。")
        except Exception as e:
            print(f"处理 {filename} 时发生错误: {e}")

    # 保存总图谱数据
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(master_graph, f, ensure_ascii=False, indent=4)
        
    print(f"\n全部处理完成！知识图谱数据已保存至 {OUTPUT_FILE}")
    print(f"共提取了 {len(master_graph['nodes'])} 个节点, {len(master_graph['edges'])} 条边和 {len(master_graph['hyperedges'])} 条超边。")

if __name__ == "__main__":
    asyncio.run(process_cases())