"""
Agno Agent API — 燃料管理系统
================================
燃料操作通过 @tool 函数直接调用知识图谱（零 HTTP 开销）
Skills 提供领域知识和使用场景指引
用法: uvicorn main:app --reload --host 0.0.0.0 --port 8005
"""

import json
import asyncio
import threading
import uuid
from pathlib import Path
from datetime import datetime

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.vllm import VLLM
from agno.os import AgentOS
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fuel_demo import init_fuel_knowledge_graph, get_kg
from fuel_tools import (
    query_fuel_status,
    query_fuel_risk,
    trace_batch_lifecycle,
    optimize_blending,
    query_blend_history,
    add_stock_pile,
    add_coal_batch,
    query_boilers,
    query_supplier_profiles,
    query_supplier_detail,
    query_pile_quality,
    query_pile_detail,
    query_knowledge_graph,
)

# ==================== 初始化知识图谱 ====================
print("[启动] 正在初始化燃料知识图谱...")
init_fuel_knowledge_graph()

# ==================== 1. 模型 ====================
model = VLLM(
    id="Qwen3.6-27B",
    api_key="123",
    base_url="http://172.168.100.146:4650/v1",
)

# ==================== 2. 精简工具列表 ====================
# 只保留实际用到的工具，去掉无关的（Gmail/Telegram/YouTube/Notion...）
TOOL_DEFS = [
    ("agno.tools.calculator",        "CalculatorTools",      {}),
    ("agno.tools.python",            "PythonTools",          {"base_dir": Path("/tmp/agno_python")}),
    ("agno.tools.shell",             "ShellTools",           {}),
    ("agno.tools.pandas",            "PandasTools",          {}),
    ("agno.tools.visualization",     "VisualizationTools",   {}),
    ("agno.tools.duckduckgo",        "DuckDuckGoTools",      {}),
]


def load_tools():
    """动态加载工具，失败跳过"""
    all_tools = []
    for mod_path, cls_name, kwargs in TOOL_DEFS:
        try:
            mod = __import__(mod_path, fromlist=[cls_name])
            tool = getattr(mod, cls_name)(**kwargs)
            all_tools.append(tool)
            print(f"  [OK] {cls_name}")
        except Exception as e:
            print(f"  [X]  {cls_name} -> {str(e)[:60]}")
    print(f"[工具] {len(all_tools)}/{len(TOOL_DEFS)} 加载成功\n")
    return all_tools


# ==================== 3. Skills（保留，提供领域知识） ====================
def load_skills():
    try:
        from agno.skills import LocalSkills, Skills
        skills_dir = Path.home() / "Desktop" / "skills"
        if skills_dir.exists():
            s = Skills(loaders=[LocalSkills(str(skills_dir))])
            print(f"[Skills] 加载了 {len(s.get_all_skills())} 个")
            return s
    except Exception as e:
        print(f"[Skills] 加载失败: {e}")
    return None


# ==================== 4. Agent 配置 ====================
instructions = """\
你是一个专业的火电厂燃料管理专家。你可以调用燃料管理工具来查询和操作燃料数据。

## 工具调用方式
你已拥有以下燃料管理工具（直接调用，不需要 curl）：
- query_fuel_status: 查询库存状态、煤堆、批次、供应商、化验结果
- query_fuel_risk: 获取自燃风险、不合格批次、高风险煤堆
- trace_batch_lifecycle(batch_id): 追踪煤批次全生命周期
- optimize_blending(target_heat, target_sulfur): 掺配优化（线性规划）
- query_blend_history(last_n): 历史掺配方案
- add_stock_pile(name, heat, sulfur, cost, remain): 添加煤堆
- add_coal_batch(...): 添加入厂煤批次
- query_boilers(): 锅炉信息和运行约束
- query_supplier_profiles(): 供应商质量画像（多跳图遍历，含平均热值/硫分/不合格批次）
- query_supplier_detail(supplier_id): 单个供应商详情与批次明细
- query_pile_quality(): 煤堆质量关联分析（标注值 vs 化验值差异）
- query_pile_detail(pile_id): 单个煤堆详情（含批次/供应商/掺配关联）
- query_knowledge_graph(cypher): 直接执行 Cypher 查询（最灵活，可根据任意问题写查询）

## 重要：优先使用 query_knowledge_graph
对于复杂、临时或写死的 tool 无法覆盖的问题，直接用 query_knowledge_graph 编写 Cypher 查询。
工具描述里有完整的图谱结构（Schema），包含所有节点类型、属性和关系。
写 Cypher 时注意: 只能写只读查询 (MATCH/RETURN)，禁止写操作 (CREATE/DELETE/SET)。

## 运行约束
- 入炉热值下限: 5000 kcal/kg
- 入炉硫分上限: 0.7%

## 回答要求
- 用户用中文交流，你用中文回复
- 燃料相关回答要包含关键数据（热值、硫分、成本、温度等）
- 对于预警类问题，必须给出处理建议
- 回答要简洁清晰
"""

db_dir = Path.home() / ".agno_agent_demo"
db_dir.mkdir(exist_ok=True)
agent_db = SqliteDb(db_file=str(db_dir / "agents.db"))

base_tools = load_tools()
agent_skills = load_skills()

# 燃料工具直接作为函数传入（Agno 自动识别为 tool）
fuel_tools = [
    query_fuel_status,
    query_fuel_risk,
    trace_batch_lifecycle,
    optimize_blending,
    query_blend_history,
    add_stock_pile,
    add_coal_batch,
    query_boilers,
    query_supplier_profiles,
    query_supplier_detail,
    query_pile_quality,
    query_pile_detail,
    query_knowledge_graph,
]

agent = Agent(
    name="燃料管理助手",
    id="fuel-assistant",
    model=model,
    tools=base_tools + fuel_tools,
    skills=agent_skills,
    instructions=instructions,
    db=agent_db,
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=10,
    markdown=True,
)

# ==================== 5. FastAPI app ====================
agent_os = AgentOS(id="chat-api", agents=[agent], db=agent_db)
app = agent_os.get_app()

# 移除 AgentOS 默认路由
AGENTOS_ROUTES_TO_REMOVE = {
    "/", "/health", "/info", "/tools",
    "/sessions", "/sessions/{session_id}", "/sessions/{session_id}/runs",
    "/sessions/{session_id}/runs/{run_id}", "/sessions/{session_id}/rename",
}
app.router.routes[:] = [
    r for r in app.router.routes
    if not (hasattr(r, "path") and r.path in AGENTOS_ROUTES_TO_REMOVE)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 静态文件 + 前端 ====================
frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    dashboard = frontend_dir / "dashboard.html"
    if dashboard.exists():
        return dashboard.read_text(encoding="utf-8")
    return "<h1>Dashboard not found</h1>"

@app.get("/chat", response_class=HTMLResponse)
async def serve_chat():
    index = frontend_dir / "index.html"
    if index.exists():
        return index.read_text(encoding="utf-8")
    return "<h1>Chat not found</h1>"

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

# ==================== 事件序列化 ====================
def event_to_dict(evt):
    event = evt.event

    if event in ("RunContent", "RunIntermediateContent"):
        data = {"content": getattr(evt, "content", "") or ""}
        reasoning = getattr(evt, "reasoning_content", "") or ""
        if reasoning:
            data["reasoning"] = reasoning
        return {"event": "content", "data": data}

    if event in ("ReasoningStarted", "ReasoningCompleted"):
        return {"event": "reasoning", "data": {"content": ""}}

    if event in ("ReasoningStep", "ReasoningContentDelta"):
        text = getattr(evt, "reasoning_content", "") or getattr(evt, "content", "") or ""
        return {"event": "reasoning", "data": {"content": text}}

    if event == "ToolCallStarted":
        tool = getattr(evt, "tool", None) or {}
        return {"event": "tool_call", "data": {
            "tool_name": getattr(tool, "tool_name", "") or "",
            "tool_args": getattr(tool, "tool_args", {}) or {},
            "tool_id": getattr(tool, "tool_call_id", "") or "",
        }}

    if event == "ToolCallCompleted":
        tool = getattr(evt, "tool", None) or {}
        return {"event": "tool_result", "data": {
            "tool_name": getattr(tool, "tool_name", "") or "",
            "content": getattr(evt, "content", "") or "",
            "is_error": False,
            "tool_id": getattr(tool, "tool_call_id", "") or "",
        }}

    if event == "ToolCallError":
        tool = getattr(evt, "tool", None) or {}
        return {"event": "tool_result", "data": {
            "tool_name": getattr(tool, "tool_name", "") or "",
            "content": getattr(evt, "error", "") or "",
            "is_error": True,
            "tool_id": getattr(tool, "tool_call_id", "") or "",
        }}

    if event == "RunCompleted":
        steps = getattr(evt, "reasoning_steps", []) or []
        text = " | ".join(getattr(s, "content", "") or "" for s in steps)
        return {"event": "run_completed", "data": {"reasoning_steps": text}}

    if event == "RunStarted":
        return {"event": "run_started", "data": {}}

    return {"event": event or "unknown", "data": {}}

# ==================== 流式聊天 ====================
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    q = asyncio.Queue()

    def run_agent():
        try:
            gen = agent.run(
                req.message,
                session_id=req.session_id,
                stream=True,
                stream_events=True,
                run_id=str(uuid.uuid4()),
            )
            for evt in gen:
                q.put_nowait(("ok", event_to_dict(evt)))
        except Exception as e:
            q.put_nowait(("error", str(e)))
        q.put_nowait(("done", None))

    t = threading.Thread(target=run_agent, daemon=True)
    t.start()

    async def generate():
        yield "event: start\n\n"
        while True:
            status, payload = await q.get()
            if status == "done":
                break
            if status == "error":
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': payload}}, ensure_ascii=False)}\n\n"
                break
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

# ==================== 辅助端点 ====================
@app.get("/tools")
async def list_tools():
    return {"tools": [
        {"name": type(t).__name__, "description": getattr(t, "__doc__", "")}
        for t in base_tools
    ], "count": len(base_tools)}

@app.get("/sessions/{session_id}/history")
async def get_history(session_id: str, last_n: int = 20):
    history = agent.get_chat_history(session_id=session_id, last_n_runs=last_n)
    return {
        "session_id": session_id,
        "messages": [{"role": m.role, "content": (m.content or "")[:500]} for m in history],
    }

@app.post("/sessions/clear")
async def clear_memory():
    db_file = db_dir / "agents.db"
    if db_file.exists():
        db_file.unlink()
        return {"status": "cleared"}
    return {"status": "already_empty"}

# ==================== 燃料 API 端点（供前端仪表盘调用） ====================
@app.get("/fuel/status")
async def fuel_status():
    return query_fuel_status()

@app.get("/fuel/lab_results")
async def get_lab_results():
    kg = get_kg()
    try:
        return {"results": kg.get_lab_results()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/fuel/init")
async def fuel_init():
    init_fuel_knowledge_graph()
    return {"status": "ok", "message": "燃料知识图谱已初始化"}

@app.get("/fuel/risk")
async def get_risk():
    return query_fuel_risk()

@app.get("/fuel/trace/{batch_id}")
async def trace_batch(batch_id: str):
    return trace_batch_lifecycle(batch_id)

@app.post("/fuel/pile")
async def add_fuel_pile(req: dict):
    return add_stock_pile(
        name=req.get("name", ""),
        heat=float(req.get("heat", 0)),
        sulfur=float(req.get("sulfur", 0)),
        cost=float(req.get("cost", 0)),
        remain=float(req.get("remain", 0)),
    )

@app.post("/fuel/batch")
async def add_fuel_batch(req: dict):
    return add_coal_batch(
        supplier_id=req.get("supplier_id", "sup_004"),
        coal_type=req.get("coal_type", "混煤"),
        mine_origin=req.get("mine_origin", "未知"),
        arrival_date=req.get("arrival_date"),
        gross_weight=float(req.get("gross_weight", 0)),
        net_weight=float(req.get("net_weight", 0)),
        heat_declared=float(req.get("heat_declared", 0)),
        sulfur_declared=float(req.get("sulfur_declared", 0)),
        cost=float(req.get("cost", 0)),
        vehicle_count=int(req.get("vehicle_count", 0)),
    )

@app.post("/fuel/optimize")
async def optimize_blend(req: dict):
    return optimize_blending(
        target_heat=float(req.get("target_heat", 5000)),
        target_sulfur=float(req.get("target_sulfur", 0.7)),
    )

@app.get("/fuel/blend_history")
async def get_blend_history(last_n: int = 10):
    return query_blend_history(last_n)

@app.get("/fuel/supplier_profiles")
async def get_supplier_profiles():
    return query_supplier_profiles()

@app.get("/fuel/supplier/{supplier_id}")
async def get_supplier_detail(supplier_id: str):
    return query_supplier_detail(supplier_id)

@app.get("/fuel/pile_quality")
async def get_pile_quality():
    return query_pile_quality()

@app.get("/fuel/pile_detail/{pile_id}")
async def get_pile_detail(pile_id: str):
    return query_pile_detail(pile_id)

@app.get("/fuel/graph")
async def get_graph_data():
    """知识图谱可视化数据 — 供前端 ECharts 渲染"""
    kg = get_kg()
    try:
        return kg.get_graph_data()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health():
    kg = get_kg()
    try:
        piles = kg.get_all_stock_piles()
        kg_status = "connected" if piles is not None else "error"
    except Exception as e:
        kg_status = f"disconnected: {str(e)[:50]}"

    return {
        "status": "ok" if kg_status == "connected" else "error",
        "kg_status": kg_status,
        "model": "Qwen3.6-27B",
        "tools_loaded": len(base_tools),
        "fuel_tools": 8,
        "fuel_skills": 5,
        "skills_loaded": len(agent_skills.get_all_skills()) if agent_skills else 0,
        "time": datetime.now().isoformat(),
    }

# ==================== 主入口 ====================
if __name__ == "__main__":
    import uvicorn

    print(f"\n{'='*60}")
    print(f"  燃料管理 Agent API")
    print(f"  工具: {len(base_tools)} 基础 + 8 燃料")
    print(f"  Skills: 5 燃料领域知识")
    print(f"  Neo4j: 已初始化")
    print(f"  http://0.0.0.0:8005")
    print(f"{'='*60}\n")

    uvicorn.run(app, host="0.0.0.0", port=8005)
