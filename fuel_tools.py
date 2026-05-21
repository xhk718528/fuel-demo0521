"""
燃料管理工具 — 直接调用知识图谱，不经过 HTTP
供 Agent 作为 @tool 使用，替代 curl 调用 /fuel/* 端点
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from fuel_demo import get_kg


def query_fuel_status() -> Dict[str, Any]:
    """获取燃料系统完整状态（煤堆、批次、供应商、化验结果）
    
    适用场景：
    - 查询库存状态、煤堆情况
    - 查看所有批次和化验结果
    - 获取供应商列表
    """
    kg = get_kg()
    try:
        return {
            "status": "ok",
            "piles": kg.get_all_stock_piles(),
            "batches": kg.get_coal_batches(),
            "suppliers": kg.get_suppliers(),
            "lab_results": kg.get_lab_results(),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def query_fuel_risk() -> Dict[str, Any]:
    """获取所有风险预警（自燃风险、不合格批次）
    
    适用场景：
    - 检查自燃风险、煤场安全
    - 查询不合格批次
    - 查看高风险煤堆
    """
    kg = get_kg()
    try:
        risk_piles = kg.get_high_risk_piles()
        unqualified = kg.get_unqualified_batches()
        return {
            "self_ignition": risk_piles,
            "unqualified": unqualified,
            "high_risk": risk_piles,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def trace_batch_lifecycle(batch_id: str) -> Dict[str, Any]:
    """追踪煤批次全生命周期（采样、制样、化验、存放）
    
    适用场景：
    - 追踪特定批次的全流程
    - 查看批次的来源、质检、存放情况
    """
    kg = get_kg()
    try:
        result = kg.trace_coal_lifecycle(batch_id)
        return {"result": result} if result else {"status": "error", "message": f"未找到批次 {batch_id}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def optimize_blending(target_heat: float = 5000, target_sulfur: float = 0.7) -> Dict[str, Any]:
    """掺配优化 — 线性规划求解最低成本掺配方案
    
    适用场景：
    - 计算最优掺配比例
    - 自定义热值和硫分约束
    
    参数：
        target_heat: 目标热值 (kcal/kg)，默认 5000
        target_sulfur: 目标硫分上限 (%)，默认 0.7
    """
    from pulp import LpProblem, LpMinimize, LpVariable, lpSum, PULP_CBC_CMD

    kg = get_kg()
    try:
        piles = kg.get_all_stock_piles()
        available = [p for p in piles if p.get("remain", 0) > 0]

        if len(available) < 2:
            return {"status": "error", "message": "至少需要 2 种可用煤堆", "piles": available}

        prob = LpProblem("BlendOptimization", LpMinimize)
        x = {p["id"]: LpVariable(f"x_{p['id']}", 0, 1) for p in available}

        prob += lpSum(x[p["id"]] * p["cost"] for p in available)
        prob += lpSum(x[p["id"]] for p in available) == 1
        prob += lpSum(x[p["id"]] * p["heat"] for p in available) >= target_heat
        prob += lpSum(x[p["id"]] * p["sulfur"] for p in available) <= target_sulfur

        prob.solve(PULP_CBC_CMD(msg=False))

        if prob.status != 1:
            return {"status": "error", "message": f"无可行方案：无法满足热值 >= {target_heat} 且 硫分 <= {target_sulfur}%"}

        blend_ratio = {}
        used_piles = []
        for p in available:
            val = x[p["id"]].varValue
            if val and val > 0.01:
                blend_ratio[p["name"]] = round(val * 100, 1)
                used_piles.append(p)

        blended_heat = round(sum(x[p["id"]].varValue * p["heat"] for p in used_piles), 1)
        blended_sulfur = round(sum(x[p["id"]].varValue * p["sulfur"] for p in used_piles), 3)
        total_cost = round(prob.objective.value(), 2)

        max_batches = []
        for p in used_piles:
            ratio = blend_ratio[p["name"]] / 100
            if ratio > 0:
                max_batches.append(p["remain"] / ratio)
        max_batch_tons = round(min(max_batches), 0) if max_batches else 0

        plan_result = {
            "blend_ratio": blend_ratio,
            "total_cost": total_cost,
            "blended_heat": blended_heat,
            "blended_sulfur": blended_sulfur,
            "max_batch_tons": max_batch_tons,
        }
        plan_id = kg.create_blend_plan(plan_result)

        details = []
        for p in used_piles:
            ratio = blend_ratio[p["name"]] / 100
            details.append({
                "pile_name": p["name"],
                "pile_id": p["id"],
                "ratio": blend_ratio[p["name"]],
                "heat_contribution": round(p["heat"] * ratio, 1),
                "sulfur_contribution": round(p["sulfur"] * ratio, 4),
                "cost_contribution": round(p["cost"] * ratio, 2),
                "available_tons": p["remain"],
            })

        return {
            "status": "ok",
            "plan_id": plan_id,
            "target_heat": target_heat,
            "target_sulfur": target_sulfur,
            "blended_heat": blended_heat,
            "blended_sulfur": blended_sulfur,
            "total_cost": total_cost,
            "max_batch_tons": max_batch_tons,
            "blend_ratio": blend_ratio,
            "details": details,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def query_blend_history(last_n: int = 10) -> Dict[str, Any]:
    """查询历史掺配方案
    
    适用场景：
    - 查看最近的掺配记录
    - 分析历史掺配效果
    """
    kg = get_kg()
    try:
        plans = kg.get_recent_blend_plans(last_n)
        return {"plans": plans}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def add_stock_pile(name: str, heat: float, sulfur: float, cost: float, remain: float) -> Dict[str, Any]:
    """添加新煤堆
    
    适用场景：
    - 新煤入库
    - 更新库存结构
    """
    kg = get_kg()
    try:
        pile_id = kg.add_stock_pile(name=name, heat=heat, sulfur=sulfur, cost=cost, remain=remain)
        if pile_id:
            return {"status": "ok", "pile_id": pile_id}
        return {"status": "error", "message": "添加失败"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def add_coal_batch(
    supplier_id: str = "sup_004",
    coal_type: str = "混煤",
    mine_origin: str = "未知",
    arrival_date: Optional[str] = None,
    gross_weight: float = 0,
    net_weight: float = 0,
    heat_declared: float = 0,
    sulfur_declared: float = 0,
    cost: float = 0,
    vehicle_count: int = 0,
) -> Dict[str, Any]:
    """添加入厂煤批次
    
    适用场景：
    - 新煤到达
    - 记录批次信息
    """
    kg = get_kg()
    try:
        batch_data = {
            "supplier_id": supplier_id,
            "coal_type": coal_type,
            "mine_origin": mine_origin,
            "arrival_date": arrival_date or datetime.now().strftime("%Y-%m-%d"),
            "gross_weight": gross_weight,
            "net_weight": net_weight,
            "vehicle_count": vehicle_count,
            "heat_declared": heat_declared,
            "sulfur_declared": sulfur_declared,
            "cost": cost,
        }
        batch_id = kg.add_coal_batch(batch_data)
        if batch_id:
            return {"status": "ok", "batch_id": batch_id}
        return {"status": "error", "message": "添加失败"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def query_boilers() -> Dict[str, Any]:
    """查询锅炉信息和运行约束
    
    适用场景：
    - 了解锅炉热值和硫分要求
    - 检查约束条件
    """
    kg = get_kg()
    try:
        return {
            "boilers": kg.get_boilers(),
            "constraints": kg.get_constraints(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def query_supplier_profiles() -> Dict[str, Any]:
    """供应商质量画像 — 多跳关联图遍历: Supplier -> CoalBatch -> LabResult
    
    适用场景：
    - 评估供应商供货质量
    - 选择可靠供应商
    - 分析供应商历史表现
    
    返回每个供应商的:
    - 总供货批次 / 不合格批次数
    - 平均热值、硫分、灰分、挥发分、水分
    - 信用评级
    - 约束违规次数
    """
    kg = get_kg()
    try:
        profiles = kg.get_supplier_profiles()
        return {
            "status": "ok",
            "profiles": profiles,
            "count": len(profiles),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def query_supplier_detail(supplier_id: str) -> Dict[str, Any]:
    """单个供应商详情 — 含批次质检明细
    
    适用场景：
    - 深入了解某供应商供货情况
    - 查看某供应商每批次的质量记录
    - 供应商准入评估
    
    参数：
        supplier_id: 供应商ID (如 sup_001)
    """
    kg = get_kg()
    try:
        detail = kg.get_supplier_detail(supplier_id)
        if detail:
            return {"status": "ok", "detail": detail}
        return {"status": "error", "message": f"未找到供应商 {supplier_id}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def query_pile_quality() -> Dict[str, Any]:
    """煤堆质量关联分析 — 反向遍历: StockPile <- CoalBatch -> LabResult
    
    适用场景：
    - 检查煤堆标注值与实际化验值的差异
    - 发现标注不准的煤堆 (热值/硫分偏高或偏低)
    - 评估煤堆真实质量 (掺配决策依据)
    
    返回每个煤堆的:
    - 标注热值 vs 化验平均热值 (差异分析)
    - 不合格批次数量
    - 关联供应商分布
    - 约束违规次数
    """
    kg = get_kg()
    try:
        quality = kg.get_pile_quality()
        return {
            "status": "ok",
            "piles": quality,
            "count": len(quality),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def query_pile_detail(pile_id: str) -> Dict[str, Any]:
    """单个煤堆详情 — 含批次、供应商、化验、掺配关联
    
    适用场景：
    - 掺配决策前深度评估煤堆
    - 了解煤堆关联的所有信息
    - 煤堆质量溯源
    
    参数：
        pile_id: 煤堆ID (如 pile_A)
    """
    kg = get_kg()
    try:
        detail = kg.get_pile_detail(pile_id)
        if detail:
            return {"status": "ok", "detail": detail}
        return {"status": "error", "message": f"未找到煤堆 {pile_id}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def query_knowledge_graph(cypher: str) -> Dict[str, Any]:
    """直接执行 Cypher 查询语句 — 在燃料知识图谱上进行任意只读查询
    
    这是最灵活的查询方式，你可以根据用户问题编写 Cypher 查询。
    
    == 图谱结构 (Schema) ==
    
    节点类型:
      Supplier {id, name, credit_rating: A/B/C}
      CoalBatch {batch_id, supplier_id, coal_type, mine_origin, arrival_date, gross_weight, net_weight, vehicle_count, heat_declared, sulfur_declared, cost}
      SamplingRecord {id, batch_id, sample_time, sampler, location}
      SamplePreparation {id, preparation_time, preparator, method}
      LabResult {id, preparation_id, heat, sulfur, ash, volatile_matter, moisture, analyst, analysis_date, is_qualified}
      StockPile {id, name, heat, sulfur, cost, remain, current_temp, alert_level, location, max_temp_history, created_time}
      TempMonitorPoint {id, temperature, reading_time, status}
      Constraint {id, name, value, unit, description}
      Boiler {id, type, rated_load, min_heat, max_sulfur, status}
      BlendPlan {id, created_at, total_cost, blended_heat, blended_sulfur, blend_ratio}
      Risk {id, risk_type, severity, description, detected_time}
      CauseCondition {id, condition_type, description}
      FurnaceRecord {id, batch_id, feed_time, load, duration}
    
    关系:
      (Supplier)-[:SUPPLIES]->(CoalBatch)
      (CoalBatch)-[:PRODUCES]->(SamplingRecord)
      (SamplingRecord)-[:PREPARED_TO]->(SamplePreparation)
      (SamplePreparation)-[:TESTED_BY]->(LabResult)
      (CoalBatch)-[:STORED_AT]->(StockPile)
      (StockPile)-[:MONITORED_BY]->(TempMonitorPoint)
      (LabResult)-[:VIOLATES]->(Constraint)
      (LabResult)-[:TRIGGERS]->(Risk)
      (Boiler)-[:REQUIRES]->(Constraint)
      (BlendPlan)-[:BLENDS_FROM]->(StockPile)
      (BlendPlan)-[:FED_TO]->(Boiler)
      (BlendPlan)-[:RECORDED_AS]->(FurnaceRecord)
      (CauseCondition)-[:LEADS_TO]->(Risk)
      (CauseCondition)-[:TRIGGERS]->(StockPile)
    
    常用查询模式:
      供应商质量: (Supplier)-[:SUPPLIES]->(CoalBatch)-[:PRODUCES]->()-[:PREPARED_TO]->()-[:TESTED_BY]->(LabResult)
      煤堆质量: (StockPile)<-[:STORED_AT]-(CoalBatch)-[:PRODUCES]->()-[:PREPARED_TO]->()-[:TESTED_BY]->(LabResult)
      不合格批次: (LabResult {is_qualified: false})<-[:TESTED_BY]-()<-[:PREPARED_TO]-()<-[:PRODUCES]-(CoalBatch)
      自燃风险: (StockPile)-[:MONITORED_BY]->(TempMonitorPoint) WHERE temp > 55
      掺配溯源: (BlendPlan)-[:BLENDS_FROM]->(StockPile)<-[:STORED_AT]-(CoalBatch)
    
    == 安全限制 ==
    - 只允许只读查询 (MATCH, RETURN)
    - 禁止写操作 (CREATE, MERGE, DELETE, REMOVE, SET)
    - 结果限制 200 行
    
    == 示例 ==
    
    查询所有煤堆:
      MATCH (p:StockPile) RETURN p.name as name, p.heat as heat, p.sulfur as sulfur, p.remain as remain
    
    查供应商 sup_001 的批次:
      MATCH (s:Supplier {id: 'sup_001'})-[:SUPPLIES]->(b:CoalBatch) RETURN b.batch_id, b.coal_type, b.arrival_date
    
    查热值低于 5000 的不合格化验:
      MATCH (l:LabResult WHERE l.heat < 5000) RETURN l.heat, l.sulfur, l.is_qualified
    
    参数:
        cypher: Cypher 查询语句 (只读)
    """
    kg = get_kg()
    try:
        return kg.execute_cypher(cypher)
    except Exception as e:
        return {"status": "error", "message": str(e)}
