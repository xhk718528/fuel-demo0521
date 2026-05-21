"""
燃料知识图谱客户端 — Neo4j 数据层
供 main.py 的 /fuel/* API 端点直接调用
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from neo4j import GraphDatabase

# ==================== Neo4j 连接配置 ====================
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7689")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "fuel")


# 全局单例，避免每个请求创建新连接
_global_kg = None

def get_kg() -> "FuelKnowledgeGraph":
    """获取全局共享的 FuelKnowledgeGraph 单例"""
    global _global_kg
    if _global_kg is None:
        _global_kg = FuelKnowledgeGraph()
    return _global_kg


class FuelKnowledgeGraph:
    """燃料知识图谱客户端 - 完整版"""

    # ==================== 图谱 Schema（模型用来写 Cypher 的参考） ====================
    SCHEMA = """
== 节点类型 ==
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

== 关系类型 ==
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

== 常用查询模式 ==
  供应商质量: (Supplier)-[:SUPPLIES]->(CoalBatch)-[:PRODUCES]->()-[:PREPARED_TO]->()-[:TESTED_BY]->(LabResult)
  煤堆质量: (StockPile)<-[:STORED_AT]-(CoalBatch)-[:PRODUCES]->()-[:PREPARED_TO]->()-[:TESTED_BY]->(LabResult)
  不合格批次: (LabResult {is_qualified: false})<-[:TESTED_BY]-()<-[:PREPARED_TO]-()<-[:PRODUCES]-(CoalBatch)
  自燃风险: (StockPile)-[:MONITORED_BY]->(TempMonitorPoint) WHERE temp > 55
  掺配溯源: (BlendPlan)-[:BLENDS_FROM]->(StockPile)<-[:STORED_AT]-(CoalBatch)
"""

    def __init__(self):
        self._driver = None
    
    def _get_driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
                database=NEO4J_DATABASE
            )
        return self._driver
    
    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    # ==================== 动态 Cypher 执行（模型写查询） ====================

    def execute_cypher(self, cypher: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """安全执行用户/模型生成的 Cypher 查询

        安全措施:
        - 只允许只读语句 (MATCH, RETURN, WITH, UNWIND, CALL)
        - 禁止写操作 (CREATE, MERGE, DELETE, REMOVE, SET, DETACH)
        - 结果行数限制 (max 200 行)
        - 属性值截断 (max 500 字符)
        - 节点对象自动序列化 (neo4j Node 不可 JSON 序列化)

        参数:
            cypher: Cypher 查询语句
            params: 可选的参数字典

        返回:
            {"status": "ok", "columns": [...], "rows": [...]}
            或 {"status": "error", "message": "..."}
        """
        # ---- 安全检查: 禁止写操作 ----
        blocked_keywords = [
            "CREATE", "MERGE", "DELETE", "REMOVE", "SET ", "DETACH",
            "LOAD CSV", "PERIODIC COMMIT", "CALL dbms.",
            "UNWIND",  # 虽然只读，但常与 CREATE/MERGE 配合
        ]
        cypher_upper = cypher.upper().strip()

        # 允许以这些关键字开头
        allowed_starts = ("MATCH", "RETURN", "CALL ", "OPTIONAL MATCH", "UNWIND")
        if not any(cypher_upper.startswith(kw) for kw in allowed_starts):
            return {"status": "error", "message": f"不支持的查询语句。只允许只读查询 (MATCH/RETURN/CALL)，禁止写操作。"}

        for kw in blocked_keywords:
            if kw in cypher_upper:
                # 允许 CALL 开头的只读调用
                if kw == "UNWIND" and cypher_upper.startswith("UNWIND"):
                    continue
                return {"status": "error", "message": f"查询包含禁止的操作: {kw}。只允许只读查询。"}

        # ---- 执行查询 ----
        try:
            with self._get_driver().session() as session:
                result = session.run(cypher, parameters=params or {})
                keys = result.keys()
                rows = []
                count = 0
                max_rows = 200
                for record in result:
                    if count >= max_rows:
                        break
                    row = {}
                    for key in keys:
                        val = record[key]
                        row[key] = self._serialize_value(val)
                    rows.append(row)
                    count += 1

                return {
                    "status": "ok",
                    "columns": list(keys),
                    "rows": rows,
                    "total_rows": count,
                    "query": cypher[:200],
                }
        except Exception as e:
            return {"status": "error", "message": f"Cypher 执行失败: {str(e)[:300]}"}

    @staticmethod
    def _serialize_value(val: Any) -> Any:
        """将 Neo4j 值类型转为 JSON 可序列化格式"""
        if val is None:
            return None
        # neo4j Node
        if hasattr(val, "labels"):
            return {"_type": "Node", "labels": list(val.labels), "properties": dict(val) if hasattr(val, "items") else {}}
        # neo4j Relationship
        if hasattr(val, "type") and hasattr(val, "start_node"):
            return {"_type": "Relationship", "type": val.type, "properties": dict(val) if hasattr(val, "items") else {}}
        # list
        if isinstance(val, list):
            return [FuelKnowledgeGraph._serialize_value(v) for v in val[:50]]
        # dict
        if isinstance(val, dict):
            return {k: FuelKnowledgeGraph._serialize_value(v) for k, v in val.items()}
        # truncate long strings
        if isinstance(val, str) and len(val) > 500:
            return val[:500] + "..."
        return val

    # ==================== 基础查询 ====================
    
    def get_all_stock_piles(self) -> List[Dict]:
        """获取所有煤堆信息"""
        query = """
        MATCH (s:StockPile)
        RETURN s.id as id, s.name as name, s.heat as heat,
               s.sulfur as sulfur, s.cost as cost, s.remain as remain,
               s.current_temp as current_temp, s.alert_level as alert_level,
               s.location as location, s.max_temp_history as max_temp_history
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[KG] 查询失败: {e}")
            return []
    
    def get_coal_batches(self) -> List[Dict]:
        """获取所有入厂煤批次（含化验结果）"""
        query = """
        MATCH (b:CoalBatch)
        OPTIONAL MATCH (b)-[:PRODUCES]->(s:SamplingRecord)-[:PREPARED_TO]->(p:SamplePreparation)-[:TESTED_BY]->(l:LabResult)
        RETURN b.batch_id as batch_id, b.supplier_id as supplier_id,
               b.coal_type as coal_type, b.arrival_date as arrival_date,
               b.net_weight as net_weight, b.heat_declared as heat_declared,
               b.sulfur_declared as sulfur_declared, b.cost as cost,
               b.mine_origin as mine_origin,
               l.id as lab_id, l.heat as lab_heat, l.sulfur as lab_sulfur,
               l.ash as lab_ash, l.volatile_matter as lab_volatile,
               l.moisture as lab_moisture, l.analyst as lab_analyst,
               l.analysis_date as lab_date, l.is_qualified as lab_qualified
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[KG] 查询批次失败: {e}")
            return []

    def get_lab_results(self) -> List[Dict]:
        """获取所有化验结果（通过关系链关联批次）"""
        query = """
        MATCH (b:CoalBatch)-[:PRODUCES]->(s:SamplingRecord)-[:PREPARED_TO]->(p:SamplePreparation)-[:TESTED_BY]->(l:LabResult)
        RETURN l.id as lab_id, b.batch_id as batch_id, b.coal_type as coal_type,
               l.heat as heat, l.sulfur as sulfur, l.ash as ash,
               l.volatile_matter as volatile_matter, l.moisture as moisture,
               l.analyst as analyst, l.analysis_date as analysis_date,
               l.is_qualified as is_qualified
        ORDER BY l.analysis_date DESC
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[KG] 查询化验结果失败: {e}")
            return []
    
    def get_suppliers(self) -> List[Dict]:
        """获取供应商列表"""
        query = "MATCH (s:Supplier) RETURN s.id as id, s.name as name, s.credit_rating as credit_rating"
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[KG] 查询供应商失败: {e}")
            return []
    
    def get_constraints(self) -> Dict:
        """获取运行约束"""
        query = "MATCH (c:Constraint) RETURN c.name as name, c.value as value"
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                return {record["name"]: record["value"] for record in result}
        except Exception as e:
            print(f"[KG] 查询约束失败: {e}")
            return {"入炉热值下限": 5000, "入炉硫分上限": 0.7}
    
    def get_boilers(self) -> List[Dict]:
        """获取锅炉信息"""
        query = "MATCH (b:Boiler) RETURN b.id as id, b.type as type, b.rated_load as rated_load, b.min_heat as min_heat, b.max_sulfur as max_sulfur"
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[KG] 查询锅炉失败: {e}")
            return []
    
    # ==================== 全流程追溯 ====================
    
    def trace_coal_lifecycle(self, batch_id: str) -> Dict:
        """追踪煤批次的全生命周期"""
        query = """
        MATCH (b:CoalBatch {batch_id: $batch_id})
        OPTIONAL MATCH (b)-[:PRODUCES]->(s:SamplingRecord)
        OPTIONAL MATCH (s)-[:PREPARED_TO]->(p:SamplePreparation)
        OPTIONAL MATCH (p)-[:TESTED_BY]->(l:LabResult)
        OPTIONAL MATCH (b)-[:STORED_AT]->(st:StockPile)
        RETURN b, collect(DISTINCT s) as samplings, 
               collect(DISTINCT p) as preparations,
               collect(DISTINCT l) as lab_results,
               collect(DISTINCT st) as stock_piles
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query, batch_id=batch_id)
                record = result.single()
                if record:
                    return {
                        "batch": dict(record["b"]) if record["b"] else None,
                        "samplings": [dict(s) for s in record["samplings"] if s],
                        "preparations": [dict(p) for p in record["preparations"] if p],
                        "lab_results": [dict(l) for l in record["lab_results"] if l],
                        "stock_piles": [dict(st) for st in record["stock_piles"] if st]
                    }
                return None
        except Exception as e:
            print(f"[KG] 追溯失败: {e}")
            return None
    
    def get_high_risk_piles(self) -> List[Dict]:
        """获取有自燃风险的煤堆"""
        query = """
        MATCH (p:StockPile)
        WHERE p.current_temp > 55 OR p.alert_level = 'warning'
        OPTIONAL MATCH (p)-[:MONITORED_BY]->(t:TempMonitorPoint)
        RETURN p.id as pile_id, p.name as name, p.current_temp as current_temp,
               p.alert_level as alert_level, p.remain as remain,
               collect(t) as monitors
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[KG] 查询风险煤堆失败: {e}")
            return []
    
    def get_unqualified_batches(self) -> List[Dict]:
        """获取化验不合格的批次"""
        query = """
        MATCH (l:LabResult)-[:VIOLATES]->(c:Constraint)
        MATCH (l)<-[:TESTED_BY]-(p:SamplePreparation)<-[:PREPARED_TO]-(s:SamplingRecord)<-[:PRODUCES]-(b:CoalBatch)
        RETURN DISTINCT b.batch_id as batch_id, l.id as lab_id, 
               l.heat as heat, l.sulfur as sulfur,
               c.name as violated_constraint, l.analysis_date as analysis_date
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[KG] 查询不合格批次失败: {e}")
            return []
    
    def get_recent_blend_plans(self, limit: int = 10) -> List[Dict]:
        """获取最近的掺配方案"""
        query = """
        MATCH (b:BlendPlan)
        OPTIONAL MATCH (b)-[:FED_TO]->(bo:Boiler)
        RETURN b.id as id, b.created_at as created_at, 
               b.blend_ratio as blend_ratio, b.total_cost as total_cost,
               b.blended_heat as blended_heat, b.blended_sulfur as blended_sulfur,
               bo.id as boiler_id
        ORDER BY b.created_at DESC
        LIMIT $limit
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query, limit=limit)
                records = []
                for r in result:
                    rec = dict(r)
                    # 解析blend_ratio JSON字符串
                    if rec.get("blend_ratio") and isinstance(rec["blend_ratio"], str):
                        try:
                            rec["blend_ratio"] = json.loads(rec["blend_ratio"])
                        except:
                            pass
                    records.append(rec)
                return records
        except Exception as e:
            print(f"[KG] 查询掺配方案失败: {e}")
            return []
    
    # ==================== 数据写入 ====================
    
    def add_coal_batch(self, batch_data: Dict) -> str:
        """添加新入厂煤批次"""
        batch_id = f"BATCH_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        query = """
        CREATE (b:CoalBatch {
            batch_id: $batch_id, supplier_id: $supplier_id, coal_type: $coal_type,
            mine_origin: $mine_origin, arrival_date: $arrival_date,
            gross_weight: $gross_weight, net_weight: $net_weight, vehicle_count: $vehicle_count,
            heat_declared: $heat_declared, sulfur_declared: $sulfur_declared, cost: $cost
        })
        RETURN b.batch_id as batch_id
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query, 
                    batch_id=batch_id,
                    supplier_id=batch_data.get("supplier_id", "sup_004"),
                    coal_type=batch_data.get("coal_type", "混煤"),
                    mine_origin=batch_data.get("mine_origin", "未知"),
                    arrival_date=batch_data.get("arrival_date", datetime.now().strftime("%Y-%m-%d")),
                    gross_weight=batch_data.get("gross_weight", 0),
                    net_weight=batch_data.get("net_weight", 0),
                    vehicle_count=batch_data.get("vehicle_count", 0),
                    heat_declared=batch_data.get("heat_declared", 0),
                    sulfur_declared=batch_data.get("sulfur_declared", 0),
                    cost=batch_data.get("cost", 0)
                )
                return result.single()["batch_id"]
        except Exception as e:
            print(f"[KG] 添加批次失败: {e}")
            return ""
    
    def add_lab_result(self, lab_data: Dict) -> str:
        """添加化验结果"""
        lab_id = f"LAB_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        query = """
        MATCH (prep:SamplePreparation {id: $preparation_id})
        CREATE (l:LabResult {
            id: $lab_id, preparation_id: $preparation_id,
            heat: $heat, sulfur: $sulfur, ash: $ash, volatile_matter: $volatile_matter,
            moisture: $moisture, analyst: $analyst, analysis_date: $analysis_date,
            is_qualified: $is_qualified
        })
        CREATE (prep)-[:TESTED_BY]->(l)
        RETURN l.id as lab_id
        """
        is_qualified = (lab_data.get("heat", 0) >= 5000 and lab_data.get("sulfur", 0) <= 0.7)
        try:
            with self._get_driver().session() as session:
                result = session.run(query,
                    lab_id=lab_id,
                    preparation_id=lab_data.get("preparation_id", ""),
                    heat=lab_data.get("heat", 0),
                    sulfur=lab_data.get("sulfur", 0),
                    ash=lab_data.get("ash", 0),
                    volatile_matter=lab_data.get("volatile_matter", 0),
                    moisture=lab_data.get("moisture", 0),
                    analyst=lab_data.get("analyst", "系统"),
                    analysis_date=lab_data.get("analysis_date", datetime.now().strftime("%Y-%m-%d")),
                    is_qualified=is_qualified
                )
                return result.single()["lab_id"]
        except Exception as e:
            print(f"[KG] 添加化验结果失败: {e}")
            return ""
    
    def add_stock_pile(self, name: str, heat: float, sulfur: float, cost: float, remain: float) -> str:
        """添加新煤堆"""
        pile_id = f"pile_{uuid.uuid4().hex[:8]}"
        query = """
        CREATE (s:StockPile {
            id: $id, name: $name, heat: $heat, sulfur: $sulfur,
            cost: $cost, remain: $remain, alert: true,
            created_time: $created_time, current_temp: $current_temp, alert_level: 'warning'
        })
        RETURN s.id as id
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query, 
                    id=pile_id, name=name, heat=heat, sulfur=sulfur,
                    cost=cost, remain=remain,
                    created_time=datetime.now().strftime("%Y-%m-%d"),
                    current_temp=35
                )
                return result.single()["id"]
        except Exception as e:
            print(f"[KG] 添加煤堆失败: {e}")
            return ""
    
    def create_blend_plan(self, plan: Dict) -> str:
        """保存掺配方案到图谱"""
        plan_id = f"BLEND_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        query = """
        CREATE (p:BlendPlan {
            id: $id, created_at: $created_at, total_cost: $total_cost,
            blended_heat: $blended_heat, blended_sulfur: $blended_sulfur,
            blend_ratio: $blend_ratio
        })
        RETURN p.id as id
        """
        try:
            with self._get_driver().session() as session:
                session.run(query,
                    id=plan_id,
                    created_at=datetime.now().isoformat(),
                    total_cost=plan.get("total_cost", 0),
                    blended_heat=plan.get("blended_heat", 0),
                    blended_sulfur=plan.get("blended_sulfur", 0),
                    blend_ratio=json.dumps(plan.get("blend_ratio", {}))
                )
            return plan_id
        except Exception as e:
            print(f"[KG] 保存掺配方案失败: {e}")
            return ""
    
    def update_pile_temperature(self, pile_id: str, temperature: float):
        """更新煤堆温度"""
        query = """
        MATCH (s:StockPile {id: $id})
        SET s.current_temp = $temp,
            s.alert_level = CASE WHEN $temp > 60 THEN 'warning' ELSE 'normal' END,
            s.last_updated = $updated
        """
        with self._get_driver().session() as session:
            session.run(query, id=pile_id, temp=temperature, updated=datetime.now().isoformat())
    
    # ==================== 推理查询 ====================
    
    def find_blendable_piles(self, target_heat: float, target_sulfur: float) -> List[Dict]:
        """寻找可掺配的煤堆组合"""
        query = """
        MATCH (s:StockPile)
        WHERE s.remain > 0 AND s.alert_level <> 'warning'
        RETURN s.name as name, s.heat as heat, s.sulfur as sulfur, 
               s.cost as cost, s.remain as remain
        ORDER BY s.cost
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[KG] 查找可掺配煤堆失败: {e}")
            return []

    # ==================== 供应商质量画像 (A) ====================

    def get_supplier_profiles(self) -> List[Dict]:
        """供应商质量画像 — 多跳关联: Supplier -> CoalBatch -> LabResult

        利用图遍历聚合供应商的历史供应质量数据，包括:
        - 总供货批次 / 不合格批次
        - 平均热值 / 硫分 / 灰分 / 挥发分
        - 是否出现过违反约束的化验结果
        """
        query = """
        MATCH (sup:Supplier)-[:SUPPLIES]->(b:CoalBatch)
          -[:PRODUCES]->(s:SamplingRecord)-[:PREPARED_TO]->(p:SamplePreparation)-[:TESTED_BY]->(l:LabResult)
        OPTIONAL MATCH (l)-[:VIOLATES]->(c:Constraint)
        WITH sup, b, l, c
        WITH sup, l, c,
             count(DISTINCT b) as total_batches
        WITH sup,
             total_batches,
             count(l) as lab_count,
             sum(CASE WHEN l.is_qualified = false THEN 1 ELSE 0 END) as unqualified_count,
             avg(l.heat) as avg_heat,
             avg(l.sulfur) as avg_sulfur,
             avg(l.ash) as avg_ash,
             avg(l.volatile_matter) as avg_volatile,
             avg(l.moisture) as avg_moisture,
             count(c) as constraint_violations
        RETURN sup.id as supplier_id,
               sup.name as supplier_name,
               sup.credit_rating as credit_rating,
               total_batches,
               unqualified_count,
               round(avg_heat, 1) as avg_heat,
               round(avg_sulfur, 4) as avg_sulfur,
               round(avg_ash, 2) as avg_ash,
               round(avg_volatile, 2) as avg_volatile_matter,
               round(avg_moisture, 2) as avg_moisture,
               constraint_violations
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[KG] 查询供应商画像失败: {e}")
            return []

    def get_supplier_detail(self, supplier_id: str) -> Dict:
        """单个供应商详情 — 含每批次的化验明细

        返回供应商基本信息 + 所有批次的完整质检记录
        """
        query = """
        MATCH (sup:Supplier {id: $supplier_id})-[:SUPPLIES]->(b:CoalBatch)
          -[:PRODUCES]->(s:SamplingRecord)-[:PREPARED_TO]->(p:SamplePreparation)-[:TESTED_BY]->(l:LabResult)
        OPTIONAL MATCH (l)-[:VIOLATES]->(c:Constraint)
        OPTIONAL MATCH (b)-[:STORED_AT]->(sp:StockPile)
        RETURN b.batch_id as batch_id,
               b.coal_type as coal_type,
               b.arrival_date as arrival_date,
               b.net_weight as net_weight,
               l.heat as lab_heat,
               l.sulfur as lab_sulfur,
               l.ash as lab_ash,
               l.is_qualified as is_qualified,
               l.analysis_date as analysis_date,
               c.name as violated_constraint,
               sp.name as stored_pile
        ORDER BY b.arrival_date DESC
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query, supplier_id=supplier_id)
                records = [dict(r) for r in result]

            # 获取供应商基本信息
            info_query = """
            MATCH (sup:Supplier {id: $supplier_id})
            RETURN sup.id as supplier_id, sup.name as supplier_name,
                   sup.credit_rating as credit_rating
            """
            with self._get_driver().session() as session:
                info = session.run(info_query, supplier_id=supplier_id).single()
                info = dict(info) if info else {}

            # 计算汇总统计
            total = len(records)
            unqualified = sum(1 for r in records if r.get("is_qualified") is False)
            heats = [r["lab_heat"] for r in records if r.get("lab_heat") is not None]
            sulfurs = [r["lab_sulfur"] for r in records if r.get("lab_sulfur") is not None]

            return {
                **info,
                "total_batches": total,
                "unqualified_count": unqualified,
                "avg_heat": round(sum(heats) / len(heats), 1) if heats else 0,
                "avg_sulfur": round(sum(sulfurs) / len(sulfurs), 4) if sulfurs else 0,
                "batch_details": records,
            }
        except Exception as e:
            print(f"[KG] 查询供应商详情失败: {e}")
            return {}

    # ==================== 煤堆质量关联 (B) ====================

    def get_pile_quality(self) -> List[Dict]:
        """煤堆-批次-质量关联分析 — 反向遍历: StockPile <- CoalBatch -> LabResult

        揭示煤堆的真实质量情况:
        - 煤堆关联批次的平均化验热值 vs 煤堆标签热值 (差异 = 标注准确性)
        - 不合格批次数量 (潜在质量问题)
        - 关联的供应商分布
        - 违反约束次数
        """
        query = """
        MATCH (p:StockPile)<-[:STORED_AT]-(b:CoalBatch)
          -[:PRODUCES]->(s:SamplingRecord)-[:PREPARED_TO]->(sp:SamplePreparation)-[:TESTED_BY]->(l:LabResult)
        OPTIONAL MATCH (l)-[:VIOLATES]->(c:Constraint)
        OPTIONAL MATCH (sup:Supplier)-[:SUPPLIES]->(b)
        WITH p, collect(DISTINCT b) as batches, collect(l) as labs,
             collect(DISTINCT sup) as suppliers, collect(c) as violations,
             avg(l.heat) as lab_avg_heat,
             avg(l.sulfur) as lab_avg_sulfur,
             sum(CASE WHEN l.is_qualified = false THEN 1 ELSE 0 END) as unqualified_count,
             count(c) as constraint_violations
        RETURN p.id as pile_id,
               p.name as pile_name,
               p.heat as declared_heat,
               p.sulfur as declared_sulfur,
               p.cost as cost,
               p.remain as remain,
               p.current_temp as current_temp,
               p.alert_level as alert_level,
               round(lab_avg_heat, 1) as lab_avg_heat,
               round(lab_avg_sulfur, 4) as lab_avg_sulfur,
               unqualified_count,
               constraint_violations,
               [s in suppliers WHERE s IS NOT NULL | s.name] as supplier_names
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query)
                records = [dict(r) for r in result]

            # 补充: 标注差异分析
            for r in records:
                declared = r.get("declared_heat") or 0
                lab_avg = r.get("lab_avg_heat") or 0
                if declared and lab_avg:
                    diff = lab_avg - declared
                    r["heat_diff"] = round(diff, 1)
                    r["heat_accuracy"] = "准确" if abs(diff) < 100 else ("偏低" if diff < 0 else "偏高")
                else:
                    r["heat_diff"] = 0
                    r["heat_accuracy"] = "无化验数据"

                declared_s = r.get("declared_sulfur") or 0
                lab_s = r.get("lab_avg_sulfur") or 0
                if declared_s and lab_s:
                    r["sulfur_diff"] = round(lab_s - declared_s, 4)
                else:
                    r["sulfur_diff"] = 0

            return records
        except Exception as e:
            print(f"[KG] 查询煤堆质量关联失败: {e}")
            return []

    def get_pile_detail(self, pile_id: str) -> Dict:
        """单个煤堆详情 — 含关联批次、供应商、化验、风险

        完整的煤堆质量画像，适合掺配决策时深度评估
        """
        query = """
        MATCH (p:StockPile {id: $pile_id})
        OPTIONAL MATCH (p)<-[:STORED_AT]-(b:CoalBatch)
          -[:PRODUCES]->(s:SamplingRecord)-[:PREPARED_TO]->(sp:SamplePreparation)-[:TESTED_BY]->(l:LabResult)
        OPTIONAL MATCH (l)-[:VIOLATES]->(c:Constraint)
        OPTIONAL MATCH (sup:Supplier)-[:SUPPLIES]->(b)
        OPTIONAL MATCH (p)-[:MONITORED_BY]->(t:TempMonitorPoint)
        OPTIONAL MATCH (bp:BlendPlan)-[:BLENDS_FROM]->(p)
        RETURN b.batch_id as batch_id,
               b.coal_type as coal_type,
               b.arrival_date as arrival_date,
               sup.name as supplier_name,
               sup.credit_rating as credit_rating,
               l.heat as lab_heat,
               l.sulfur as lab_sulfur,
               l.ash as lab_ash,
               l.is_qualified as is_qualified,
               c.name as violated_constraint,
               t as monitor,
               collect(DISTINCT bp.id) as blend_plan_ids
        """
        try:
            with self._get_driver().session() as session:
                result = session.run(query, pile_id=pile_id)
                batch_records = [dict(r) for r in result]

            # 获取煤堆基本信息
            info_query = """
            MATCH (p:StockPile {id: $pile_id})
            RETURN p.name as name, p.heat as heat, p.sulfur as sulfur,
                   p.cost as cost, p.remain as remain,
                   p.current_temp as current_temp, p.alert_level as alert_level,
                   p.location as location
            """
            with self._get_driver().session() as session:
                info = session.run(info_query, pile_id=pile_id).single()
                info = dict(info) if info else {}

            # 聚合统计
            heats = [r["lab_heat"] for r in batch_records if r.get("lab_heat") is not None]
            sulfurs = [r["lab_sulfur"] for r in batch_records if r.get("lab_sulfur") is not None]
            all_blend_ids = set()
            for r in batch_records:
                if r.get("blend_plan_ids"):
                    all_blend_ids.update(r["blend_plan_ids"])

            # 清理 monitor 字段 (neo4j Node 对象不可序列化)
            for r in batch_records:
                r["monitor"] = None

            return {
                **info,
                "lab_avg_heat": round(sum(heats) / len(heats), 1) if heats else 0,
                "lab_avg_sulfur": round(sum(sulfurs) / len(sulfurs), 4) if sulfurs else 0,
                "heat_diff": round((sum(heats) / len(heats)) - (info.get("heat") or 0), 1) if heats else 0,
                "total_batches": len(batch_records),
                "unqualified_count": sum(1 for r in batch_records if r.get("is_qualified") is False),
                "blend_plans": list(all_blend_ids),
                "batch_details": batch_records,
            }
        except Exception as e:
            print(f"[KG] 查询煤堆详情失败: {e}")
            return {}
    
    def get_graph_data(self, depth: int = 2) -> Dict[str, Any]:
        """获取知识图谱可视化数据 — 返回节点和关系列表

        用于前端 ECharts 力导向图渲染。
        只取核心节点类型，避免图太乱。
        """
        query = """
        MATCH paths = (
            s:Supplier)-[:SUPPLIES*1..$depth]->(
            b:CoalBatch)-[:PRODUCES*1..$depth]->(
            sr:SamplingRecord)-[:PREPARED_TO*1..$depth]->(
            sp:SamplePreparation)-[:TESTED_BY*1..$depth]->(
            l:LabResult)
        OPTIONAL MATCH (b)-[:STORED_AT*1..$depth]->(p:StockPile)
        OPTIONAL MATCH (p)-[:MONITORED_BY*1..$depth]->(t:TempMonitorPoint)
        OPTIONAL MATCH (l)-[:VIOLATES*1..$depth]->(c:Constraint)
        OPTIONAL MATCH (l)-[:TRIGGERS*1..$depth]->(r:Risk)
        OPTIONAL MATCH (bp:BlendPlan)-[:BLENDS_FROM*1..$depth]->(p2:StockPile)
        OPTIONAL MATCH (bp)-[:FED_TO*1..$depth]->(bo:Boiler)
        RETURN paths
        """
        # 简化版：直接取所有核心节点 + 关系
        nodes_query = """
        MATCH (n)
        WHERE any(label in labels(n) WHERE label IN [
            'Supplier', 'CoalBatch', 'SamplingRecord', 'SamplePreparation',
            'LabResult', 'StockPile', 'TempMonitorPoint', 'Constraint',
            'Risk', 'BlendPlan', 'Boiler', 'CauseCondition', 'FurnaceRecord'
        ])
        RETURN n
        """
        rels_query = """
        MATCH (a)-[r]->(b)
        WHERE any(labelA in labels(a) WHERE labelA IN [
            'Supplier', 'CoalBatch', 'SamplingRecord', 'SamplePreparation',
            'LabResult', 'StockPile', 'TempMonitorPoint', 'Constraint',
            'Risk', 'BlendPlan', 'Boiler', 'CauseCondition', 'FurnaceRecord'
        ])
        AND any(labelB in labels(b) WHERE labelB IN [
            'Supplier', 'CoalBatch', 'SamplingRecord', 'SamplePreparation',
            'LabResult', 'StockPile', 'TempMonitorPoint', 'Constraint',
            'Risk', 'BlendPlan', 'Boiler', 'CauseCondition', 'FurnaceRecord'
        ])
        RETURN a, r, b
        """
        try:
            with self._get_driver().session() as session:
                # 节点
                nodes = []
                node_id_map = {}  # neo4j id -> index in nodes list
                for record in session.run(nodes_query):
                    n = record["n"]
                    nid = str(id(n))
                    labels = list(n.labels)
                    props = dict(n)
                    # 生成可读的 ID 和名称
                    node_id = self._get_node_id(props, labels)
                    node_name = self._get_node_name(props, labels)
                    category = self._get_node_category(labels[0] if labels else "Unknown")

                    node_obj = {
                        "id": node_id,
                        "name": node_name,
                        "category": category,
                        "props": {k: v for k, v in props.items() if k not in ("id", "name") and v is not None},
                    }
                    nodes.append(node_obj)
                    node_id_map[node_id] = len(nodes) - 1

                # 关系
                links = []
                for record in session.run(rels_query):
                    a = record["a"]
                    r = record["r"]
                    b = record["b"]
                    src_id = self._get_node_id(dict(a), list(a.labels))
                    tgt_id = self._get_node_id(dict(b), list(b.labels))
                    rel_type = r.type

                    link = {
                        "source": src_id,
                        "target": tgt_id,
                        "name": rel_type,
                    }
                    # 如果有关系属性也带上
                    rel_props = dict(r)
                    rel_props.pop("start_node", None)
                    rel_props.pop("end_node", None)
                    if rel_props:
                        link["props"] = rel_props
                    links.append(link)

                return {
                    "status": "ok",
                    "nodes": nodes,
                    "links": links,
                    "stats": {
                        "total_nodes": len(nodes),
                        "total_relations": len(links),
                    }
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _get_node_id(props: Dict, labels: List[str]) -> str:
        """从节点属性中提取唯一 ID"""
        # 优先用 id / batch_id 等字段
        for key in ("id", "batch_id", "name"):
            if key in props and props[key]:
                label = labels[0] if labels else ""
                return f"{label}:{props[key]}"
        # fallback
        return str(props.get("id", "unknown"))

    @staticmethod
    def _get_node_name(props: Dict, labels: List[str]) -> str:
        """生成节点显示名称"""
        label = labels[0] if labels else "Unknown"
        # 优先用有意义的字段组合
        if label == "Supplier":
            return props.get("name", props.get("id", ""))
        elif label == "CoalBatch":
            return f"{props.get('batch_id', '')} ({props.get('coal_type', '')})"
        elif label == "StockPile":
            return props.get("name", props.get("id", ""))
        elif label == "LabResult":
            return f"热值:{props.get('heat', '')} 硫分:{props.get('sulfur', '')}"
        elif label == "SamplingRecord":
            return f"采样:{props.get('id', '')}"
        elif label == "SamplePreparation":
            return f"制样:{props.get('id', '')}"
        elif label == "BlendPlan":
            return f"掺配:{props.get('id', '')}"
        elif label == "Boiler":
            return f"{props.get('type', '')}锅炉 ({props.get('id', '')})"
        elif label == "Constraint":
            return props.get("name", props.get("id", ""))
        elif label == "Risk":
            return f"{props.get('risk_type', '')}:{props.get('severity', '')}"
        elif label == "TempMonitorPoint":
            return f"温度:{props.get('temperature', '')}°C"
        elif label == "CauseCondition":
            return props.get("condition_type", props.get("id", ""))
        elif label == "FurnaceRecord":
            return f"入炉:{props.get('id', '')}"
        else:
            return props.get("name", props.get("id", label))

    @staticmethod
    def _get_node_category(label: str) -> str:
        """节点分类（用于 ECharts 分类颜色）"""
        category_map = {
            "Supplier": "供应商",
            "CoalBatch": "煤批次",
            "SamplingRecord": "采样记录",
            "SamplePreparation": "制样",
            "LabResult": "化验结果",
            "StockPile": "煤堆",
            "TempMonitorPoint": "测温点",
            "Constraint": "约束条件",
            "Risk": "风险",
            "BlendPlan": "掺配方案",
            "Boiler": "锅炉",
            "CauseCondition": "原因条件",
            "FurnaceRecord": "入炉记录",
        }
        return category_map.get(label, label)

    def init_demo_data(self):
        """初始化演示数据（使用Cypher文件）"""
        existing = self.get_all_stock_piles()
        if existing:
            print(f"[KG] 已有 {len(existing)} 个煤堆，跳过初始化")
            return
        
        print("[KG] 演示数据需要通过Cypher脚本初始化")
        print(f"[KG] 请执行: cypher-shell -a {NEO4J_URI} -u {NEO4J_USER} -p *** < init_data.cypher")


# ==================== 初始化函数 ====================

def init_fuel_knowledge_graph():
    """初始化燃料知识图谱"""
    kg = FuelKnowledgeGraph()
    kg.init_demo_data()
    kg.close()
    print("[燃料] 知识图谱初始化完成")
