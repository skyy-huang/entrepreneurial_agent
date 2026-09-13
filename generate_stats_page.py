"""
知识图谱 & 超图节点统计可视化页面生成器
读取 master_graph.json，生成一个包含丰富统计图表的 HTML 页面
"""
import json
import os
from collections import Counter

def load_graph_data():
    json_path = os.path.join(os.path.dirname(__file__), "data", "master_graph.json")
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def compute_stats(data):
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    hyperedges = data.get("hyperedges", [])

    # 节点类型分布
    node_type_counter = Counter(n.get("type", "未知") for n in nodes)
    node_type_sorted = node_type_counter.most_common()

    # 来源文件分布
    source_counter = Counter(n.get("source_file", "未知") for n in nodes)
    source_sorted = source_counter.most_common(10)
    
    # 行业领域和级别分布
    industry_counter = Counter(n.get("industry", "未知") for n in nodes if n.get("industry"))
    level_counter = Counter(n.get("level", "未知") for n in nodes if n.get("level"))

    # 关系类型分布
    rel_counter = Counter(e.get("relation", "未知") for e in edges)
    rel_sorted = rel_counter.most_common(15)

    # 超边节点数分布
    he_sizes = [len(h.get("nodes", [])) for h in hyperedges]
    he_size_counter = Counter(he_sizes)

    # 节点度数分布 (出度+入度)
    degree = Counter()
    for e in edges:
        degree[e.get("source", "")] += 1
        degree[e.get("target", "")] += 1
    top_degree_nodes = degree.most_common(15)

    # 超边中节点参与频次
    he_node_freq = Counter()
    for h in hyperedges:
        for nid in h.get("nodes", []):
            he_node_freq[nid] += 1
    top_he_nodes = he_node_freq.most_common(10)

    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_hyperedges": len(hyperedges),
        "node_type_dist": node_type_sorted,
        "source_dist": source_sorted,
        "rel_dist": rel_sorted,
        "he_size_dist": sorted(he_size_counter.items()),
        "top_degree_nodes": top_degree_nodes,
        "top_he_nodes": top_he_nodes,
        "avg_he_size": round(sum(he_sizes) / max(len(he_sizes), 1), 1),
        "max_he_size": max(he_sizes) if he_sizes else 0,
        "min_he_size": min(he_sizes) if he_sizes else 0,
        "unique_sources": len(source_counter),
        "unique_rel_types": len(rel_counter),
        "industry_dist": industry_counter.most_common(),
        "level_dist": level_counter.most_common()
    }

def get_stats_json():
    """供 API 调用，返回统计数据的字典"""
    data = load_graph_data()
    stats = compute_stats(data)
    # 转换为 JSON-safe 格式
    return {
        "total_nodes": stats["total_nodes"],
        "total_edges": stats["total_edges"],
        "total_hyperedges": stats["total_hyperedges"],
        "avg_he_size": stats["avg_he_size"],
        "max_he_size": stats["max_he_size"],
        "min_he_size": stats["min_he_size"],
        "unique_sources": stats["unique_sources"],
        "unique_rel_types": stats["unique_rel_types"],
        "industry_dist": [{"name": k, "value": v} for k, v in stats.get("industry_dist", [])],
        "level_dist": [{"name": k, "value": v} for k, v in stats.get("level_dist", [])],
        "node_type_dist": [{"name": k, "value": v} for k, v in stats["node_type_dist"]],
        "source_dist": [{"name": k[:20], "value": v} for k, v in stats["source_dist"]],
        "rel_dist": [{"name": k, "value": v} for k, v in stats["rel_dist"]],
        "he_size_dist": [{"size": s, "count": c} for s, c in stats["he_size_dist"]],
        "top_degree_nodes": [{"name": k[:16], "degree": v} for k, v in stats["top_degree_nodes"]],
        "top_he_nodes": [{"name": k[:16], "freq": v} for k, v in stats["top_he_nodes"]],
    }

def generate_html():
    data = load_graph_data()
    stats = compute_stats(data)
    stats_json = json.dumps(get_stats_json(), ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>知识图谱 & 超图统计分析</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body,html{{width:100%;min-height:100vh;background:#0a0e1a;color:#e2e8f0;font-family:'Inter',sans-serif}}
.page-header{{background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 50%,#0f172a 100%);padding:40px 48px 32px;border-bottom:1px solid rgba(99,102,241,.2)}}
.page-header h1{{font-size:28px;font-weight:700;background:linear-gradient(135deg,#818cf8,#38bdf8,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}}
.page-header p{{color:#94a3b8;font-size:14px}}
.nav-back{{display:inline-flex;align-items:center;gap:6px;color:#818cf8;text-decoration:none;font-size:13px;margin-bottom:16px;transition:color .2s}}
.nav-back:hover{{color:#a5b4fc}}
.kpi-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;padding:24px 48px}}
.kpi-card{{background:linear-gradient(145deg,rgba(30,27,75,.6),rgba(15,23,42,.8));border:1px solid rgba(99,102,241,.15);border-radius:14px;padding:20px 24px;text-align:center;transition:transform .25s,border-color .25s}}
.kpi-card:hover{{transform:translateY(-3px);border-color:rgba(99,102,241,.4)}}
.kpi-val{{font-size:32px;font-weight:700;background:linear-gradient(135deg,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.kpi-label{{font-size:12px;color:#94a3b8;margin-top:6px;text-transform:uppercase;letter-spacing:.5px}}
.charts-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;padding:8px 48px 48px}}
.chart-card{{background:rgba(15,23,42,.7);border:1px solid rgba(99,102,241,.12);border-radius:14px;padding:24px;backdrop-filter:blur(12px);transition:border-color .3s}}
.chart-card:hover{{border-color:rgba(99,102,241,.3)}}
.chart-card.full-width{{grid-column:1/-1}}
.chart-title{{font-size:15px;font-weight:600;color:#c7d2fe;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
.chart-title .icon{{width:28px;height:28px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px}}
.chart-box{{width:100%;height:340px}}
.chart-box.tall{{height:400px}}
@media(max-width:900px){{.charts-grid{{grid-template-columns:1fr}}.kpi-row{{grid-template-columns:repeat(2,1fr)}}.page-header,.kpi-row,.charts-grid{{padding-left:20px;padding-right:20px}}}}
</style>
</head>
<body>
<div class="page-header">
  <a href="/" class="nav-back">← 返回主页</a>
  <h1>📊 知识图谱 & 超图节点统计分析</h1>
  <p>基于顶级赛事标杆项目知识库（互联网+/挑战杯）百强项目数据</p>
</div>

<div class="kpi-row">
  <div class="kpi-card"><div class="kpi-val" id="kpiNodes">--</div><div class="kpi-label">总节点数</div></div>
  <div class="kpi-card"><div class="kpi-val" id="kpiEdges">--</div><div class="kpi-label">关系边数</div></div>
  <div class="kpi-card"><div class="kpi-val" id="kpiHE">--</div><div class="kpi-label">超图逻辑簇</div></div>
  <div class="kpi-card"><div class="kpi-val" id="kpiSrc">--</div><div class="kpi-label">标杆项目来源</div></div>
  <div class="kpi-card"><div class="kpi-val" id="kpiRel">--</div><div class="kpi-label">关系类型数</div></div>
  <div class="kpi-card"><div class="kpi-val" id="kpiAvgHE">--</div><div class="kpi-label">簇均节点数</div></div>
</div>

<div class="charts-grid">
  <!-- 行业分布 -->
  <div class="chart-card">
    <div class="chart-title"><span class="icon" style="background:rgba(99,102,241,.15);color:#818cf8">🏢</span>行业领域分布 (Industry)</div>
    <div class="chart-box" id="chartIndustry"></div>
  </div>
  
  <!-- 层级分布 -->
  <div class="chart-card">
    <div class="chart-title"><span class="icon" style="background:rgba(245,158,11,.15);color:#fbbf24">🎓</span>项目级别分布 (Level)</div>
    <div class="chart-box" id="chartLevel"></div>
  </div>

  <div class="chart-card"><div class="chart-title"><span class="icon" style="background:rgba(99,102,241,.2)">🧩</span>节点类型分布</div><div class="chart-box" id="chartNodeType"></div></div>
  <div class="chart-card"><div class="chart-title"><span class="icon" style="background:rgba(56,189,248,.2)">🔗</span>关系类型 TOP-15</div><div class="chart-box" id="chartRelType"></div></div>
  <div class="chart-card"><div class="chart-title"><span class="icon" style="background:rgba(167,139,250,.2)">⭐</span>节点度数 TOP-15</div><div class="chart-box" id="chartDegree"></div></div>
  <div class="chart-card"><div class="chart-title"><span class="icon" style="background:rgba(251,191,36,.2)">📂</span>标杆项目来源 TOP-10</div><div class="chart-box" id="chartSource"></div></div>
  <div class="chart-card"><div class="chart-title"><span class="icon" style="background:rgba(52,211,153,.2)">🌐</span>超图逻辑簇规模分布</div><div class="chart-box" id="chartHESize"></div></div>
  <div class="chart-card"><div class="chart-title"><span class="icon" style="background:rgba(244,114,182,.2)">🔥</span>超图高频参与节点 TOP-10</div><div class="chart-box" id="chartHEFreq"></div></div>
  <div class="chart-card full-width"><div class="chart-title"><span class="icon" style="background:rgba(99,102,241,.2)">🕸️</span>知识图谱全局力导向视图（可交互）</div><div class="chart-box tall" id="chartForce"></div></div>
</div>

<script>
const S = {stats_json};
// KPI
document.getElementById('kpiNodes').textContent = S.total_nodes;
document.getElementById('kpiEdges').textContent = S.total_edges;
document.getElementById('kpiHE').textContent = S.total_hyperedges;
document.getElementById('kpiSrc').textContent = S.unique_sources;
document.getElementById('kpiRel').textContent = S.unique_rel_types;
document.getElementById('kpiAvgHE').textContent = S.avg_he_size;

const COLORS = ['#818cf8','#38bdf8','#a78bfa','#34d399','#fbbf24','#f472b6','#fb923c','#22d3ee','#c084fc','#4ade80','#facc15','#f87171','#2dd4bf','#e879f9','#60a5fa'];
const darkTheme = {{ backgroundColor:'transparent', textStyle:{{color:'#94a3b8'}}, tooltip:{{backgroundColor:'rgba(15,23,42,.95)',borderColor:'#334155',textStyle:{{color:'#e2e8f0'}}}} }};

// 1. 行业分布 - 饼图
echarts.init(document.getElementById('chartIndustry')).setOption({{...darkTheme,
  series:[{{type:'pie',radius:['0%','60%'],center:['50%','52%'],
    data:(S.industry_dist||[]).map((d,i)=>({{value:d.value,name:d.name,itemStyle:{{color:COLORS[i%COLORS.length]}}}})),
    label:{{color:'#cbd5e1',fontSize:10,formatter:'{{b}}\\n{{c}}个'}},itemStyle:{{borderRadius:2,borderColor:'#0a0e1a',borderWidth:1}}}}]
}});

// 2. 层级分布 - 玫瑰图
echarts.init(document.getElementById('chartLevel')).setOption({{...darkTheme,
  series:[{{type:'pie',roseType:'area',radius:['20%','70%'],center:['50%','52%'],
    data:(S.level_dist||[]).map((d,i)=>({{value:d.value,name:d.name,itemStyle:{{color:COLORS[(i+3)%COLORS.length]}}}})),
    label:{{color:'#cbd5e1',fontSize:11}},itemStyle:{{borderRadius:6,borderColor:'#0a0e1a',borderWidth:2}}}}]
}});

// 3. 节点类型 - 玫瑰图
echarts.init(document.getElementById('chartNodeType')).setOption({{...darkTheme,
  series:[{{type:'pie',roseType:'area',radius:['20%','70%'],center:['50%','52%'],
    data:S.node_type_dist.map((d,i)=>({{value:d.value,name:d.name,itemStyle:{{color:COLORS[i%COLORS.length]}}}})),
    label:{{color:'#cbd5e1',fontSize:11}},itemStyle:{{borderRadius:6,borderColor:'#0a0e1a',borderWidth:2}}}}]
}});

// 2. 关系类型 - 横向柱状图
echarts.init(document.getElementById('chartRelType')).setOption({{...darkTheme,
  grid:{{left:120,right:30,top:10,bottom:30}},
  xAxis:{{type:'value',splitLine:{{lineStyle:{{color:'rgba(99,102,241,.1)'}}}}}},
  yAxis:{{type:'category',data:S.rel_dist.map(d=>d.name).reverse(),axisLabel:{{color:'#94a3b8',fontSize:10,width:100,overflow:'truncate'}}}},
  series:[{{type:'bar',data:S.rel_dist.map(d=>d.value).reverse(),barWidth:14,
    itemStyle:{{borderRadius:[0,6,6,0],color:new echarts.graphic.LinearGradient(0,0,1,0,[{{offset:0,color:'#6366f1'}},{{offset:1,color:'#38bdf8'}}])}},
    label:{{show:true,position:'right',color:'#94a3b8',fontSize:10}}}}]
}});

// 3. 度数 TOP - 柱状图
echarts.init(document.getElementById('chartDegree')).setOption({{...darkTheme,
  grid:{{left:130,right:30,top:10,bottom:30}},
  xAxis:{{type:'value',splitLine:{{lineStyle:{{color:'rgba(99,102,241,.1)'}}}}}},
  yAxis:{{type:'category',data:S.top_degree_nodes.map(d=>d.name).reverse(),axisLabel:{{color:'#94a3b8',fontSize:10}}}},
  series:[{{type:'bar',data:S.top_degree_nodes.map(d=>d.degree).reverse(),barWidth:14,
    itemStyle:{{borderRadius:[0,6,6,0],color:new echarts.graphic.LinearGradient(0,0,1,0,[{{offset:0,color:'#a78bfa'}},{{offset:1,color:'#f472b6'}}])}},
    label:{{show:true,position:'right',color:'#94a3b8',fontSize:10}}}}]
}});

// 4. 来源 - 环形图
echarts.init(document.getElementById('chartSource')).setOption({{...darkTheme,
  series:[{{type:'pie',radius:['38%','68%'],center:['50%','52%'],
    data:S.source_dist.map((d,i)=>({{value:d.value,name:d.name,itemStyle:{{color:COLORS[i%COLORS.length]}}}})),
    label:{{color:'#cbd5e1',fontSize:10,formatter:'{{b}}\\n{{c}}个'}},itemStyle:{{borderRadius:4,borderColor:'#0a0e1a',borderWidth:2}}}}]
}});

// 5. 超图规模分布 - 柱状图
echarts.init(document.getElementById('chartHESize')).setOption({{...darkTheme,
  grid:{{left:50,right:30,top:20,bottom:40}},
  xAxis:{{type:'category',data:S.he_size_dist.map(d=>d.size+'个节点'),axisLabel:{{color:'#94a3b8'}}}},
  yAxis:{{type:'value',splitLine:{{lineStyle:{{color:'rgba(99,102,241,.1)'}}}}}},
  series:[{{type:'bar',data:S.he_size_dist.map(d=>d.count),barWidth:28,
    itemStyle:{{borderRadius:[6,6,0,0],color:new echarts.graphic.LinearGradient(0,1,0,0,[{{offset:0,color:'#34d399'}},{{offset:1,color:'#22d3ee'}}])}},
    label:{{show:true,position:'top',color:'#94a3b8'}}}}]
}});

// 6. 超图高频节点 - 柱状图
echarts.init(document.getElementById('chartHEFreq')).setOption({{...darkTheme,
  grid:{{left:130,right:30,top:10,bottom:30}},
  xAxis:{{type:'value',splitLine:{{lineStyle:{{color:'rgba(99,102,241,.1)'}}}}}},
  yAxis:{{type:'category',data:S.top_he_nodes.map(d=>d.name).reverse(),axisLabel:{{color:'#94a3b8',fontSize:10}}}},
  series:[{{type:'bar',data:S.top_he_nodes.map(d=>d.freq).reverse(),barWidth:14,
    itemStyle:{{borderRadius:[0,6,6,0],color:new echarts.graphic.LinearGradient(0,0,1,0,[{{offset:0,color:'#fbbf24'}},{{offset:1,color:'#f472b6'}}])}},
    label:{{show:true,position:'right',color:'#94a3b8',fontSize:10}}}}]
}});

// 7. 力导向图 - 通过 API 异步加载
const forceChart = echarts.init(document.getElementById('chartForce'));
forceChart.showLoading({{text:'加载图谱数据…',color:'#818cf8',maskColor:'rgba(10,14,26,0.8)'}});
fetch('/api/graph-data').then(r=>r.json()).then(graphData=>{{
  forceChart.hideLoading();
  const cats = [...new Set(graphData.nodes.map(n=>n.type))].concat(['📜逻辑超边']);
  const catMap = Object.fromEntries(cats.map((c,i)=>[c,i]));
  const nodeIds = new Set(graphData.nodes.map(n=>n.id));
  
  let heNodes = [];
  let heEdges = [];
  if(graphData.hyperedges) {{
     graphData.hyperedges.forEach((he, idx) => {{
         const heId = 'HE_' + encodeURIComponent(he.id) + '_' + idx;
         heNodes.push({{name: heId, category: catMap['📜逻辑超边'], symbolSize: 22, itemStyle: {{color: '#fbbf24', borderColor: '#b45309', borderWidth: 2}}, label: {{show: true, formatter: '超边', color: '#fff', fontSize:10}}, desc: he.description || he.rule_name || he.id }});
         const connectedNodes = he.nodes || he.entities || [];
         connectedNodes.forEach(ent => {{
             if (nodeIds.has(ent)) {{
                 heEdges.push({{source: heId, target: ent, lineStyle: {{type: 'dashed', color: '#fbbf24'}}}});
             }}
         }});
     }});
  }}

  const finalNodes = graphData.nodes.map(n=>({{name:n.id,category:catMap[n.type],symbolSize:n.type==='解决方案'?18:10,label:{{show:false}}}})).concat(heNodes);
  const finalEdges = graphData.edges.map(e=>({{source:e.source,target:e.target}})).concat(heEdges);

  forceChart.setOption({{
    backgroundColor:'transparent',
    tooltip:{{trigger:'item',backgroundColor:'rgba(15,23,42,.95)',borderColor:'#334155',textStyle:{{color:'#e2e8f0'}},
      formatter: function(p) {{ 
        if(p.data.desc) {{
            let t = p.data.name;
            if(t.startsWith('HE_')) {{
                try {{ t = decodeURIComponent(t.substring(3, t.lastIndexOf('_'))); }} catch(e) {{}}
            }}
            return '<div style="white-space:normal;word-break:break-all;max-width:400px;line-height:1.5;">' +
                   '<div style="color:#fbbf24;font-weight:bold;font-size:13px;margin-bottom:6px;">' + t + '</div>' +
                   '<div style="color:#cbd5e1;font-size:12px;">' + p.data.desc + '</div></div>';
        }}
        return p.data.name; 
      }}
    }},
    legend:{{data:cats,textStyle:{{color:'#94a3b8'}},bottom:5,type:'scroll'}},
    series:[{{type:'graph',layout:'force',roam:true,
      data: finalNodes,
      links: finalEdges,
      categories:cats.map((c,i)=>({{name:c,itemStyle:{{color:COLORS[i%COLORS.length]}}}})),
      force:{{repulsion:300,edgeLength:100,gravity:0.05}},
      lineStyle:{{color:'source',curveness:0.2,opacity:0.3,width:0.8}},
      emphasis:{{focus:'adjacency',lineStyle:{{width:3,opacity:1}},label:{{show:true,color:'#f8fafc',fontSize:12}}}}
    }}]
  }});
}}).catch(e=>{{
  forceChart.hideLoading();
  console.error("Force chart error:", e);
  document.getElementById('chartForce').innerHTML='<div style="color:#f87171;padding:20px;word-wrap:break-word;">图谱数据加载失败: ' + String(e) + '<br/>' + (e.stack || '') + '</div>';
}});
window.addEventListener('resize',()=>{{
  document.querySelectorAll('.chart-box').forEach(el=>{{const c=echarts.getInstanceByDom(el);c&&c.resize();}});
}});
</script>
</body>
</html>"""
    out_path = os.path.join(os.path.dirname(__file__), "frontend", "graph_stats.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated: {out_path}")
    return out_path

if __name__ == "__main__":
    generate_html()
