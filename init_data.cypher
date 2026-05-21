/* ===================================================== */
/* 火电厂燃料管理知识图谱 - 完整初始化脚本（修复版） */
/* 执行方式: cat init_demo_data.cypher | docker exec -i neo4j-demo bin/cypher-shell -u neo4p -p password123 --format plain */
/* 注意：确保cypher文件保存为UTF-8编码 */
/* ===================================================== */

/* 清理现有数据 */
MATCH (n) DETACH DELETE n;

/* ==================== 1. 创建供应商 ==================== */
CREATE (s1:Supplier {id: "sup_001", name: "晋能控股", credit_rating: "A", history_performance: 0.95});
CREATE (s2:Supplier {id: "sup_002", name: "中煤集团", credit_rating: "A", history_performance: 0.92});
CREATE (s3:Supplier {id: "sup_003", name: "陕西煤业", credit_rating: "B", history_performance: 0.85});
CREATE (s4:Supplier {id: "sup_004", name: "地方小窑", credit_rating: "C", history_performance: 0.70});

/* ==================== 2. 创建入厂煤批次 ==================== */
CREATE (b1:CoalBatch {
    batch_id: "BATCH_001", supplier_id: "sup_001", coal_type: "优混煤", mine_origin: "大同",
    arrival_date: "2025-05-10", gross_weight: 3500, net_weight: 3450, vehicle_count: 115,
    heat_declared: 5200, sulfur_declared: 0.55, cost: 680
});
CREATE (b2:CoalBatch {
    batch_id: "BATCH_002", supplier_id: "sup_001", coal_type: "优混煤", mine_origin: "大同",
    arrival_date: "2025-05-12", gross_weight: 3200, net_weight: 3150, vehicle_count: 105,
    heat_declared: 5200, sulfur_declared: 0.55, cost: 680
});
CREATE (b3:CoalBatch {
    batch_id: "BATCH_003", supplier_id: "sup_002", coal_type: "洗中煤", mine_origin: "平朔",
    arrival_date: "2025-05-08", gross_weight: 5000, net_weight: 4920, vehicle_count: 164,
    heat_declared: 4800, sulfur_declared: 0.95, cost: 590
});
CREATE (b4:CoalBatch {
    batch_id: "BATCH_004", supplier_id: "sup_002", coal_type: "动力煤", mine_origin: "平朔",
    arrival_date: "2025-05-15", gross_weight: 4500, net_weight: 4430, vehicle_count: 148,
    heat_declared: 5500, sulfur_declared: 0.68, cost: 650
});
CREATE (b5:CoalBatch {
    batch_id: "BATCH_005", supplier_id: "sup_003", coal_type: "长焰煤", mine_origin: "神木",
    arrival_date: "2025-05-05", gross_weight: 3800, net_weight: 3750, vehicle_count: 125,
    heat_declared: 5800, sulfur_declared: 0.42, cost: 750
});
CREATE (b6:CoalBatch {
    batch_id: "BATCH_006", supplier_id: "sup_004", coal_type: "地方煤", mine_origin: "本地",
    arrival_date: "2025-05-14", gross_weight: 2000, net_weight: 1960, vehicle_count: 65,
    heat_declared: 4200, sulfur_declared: 1.20, cost: 520
});

/* ==================== 3. 创建采样记录 ==================== */
CREATE (sam1:SamplingRecord {
    id: "SAM_001", batch_id: "BATCH_001", sampling_point: "汽车卸煤沟", sampling_method: "机械采样",
    sample_count: 35, sampler: "张三", sampling_date: "2025-05-10"
});
CREATE (sam2:SamplingRecord {
    id: "SAM_002", batch_id: "BATCH_002", sampling_point: "汽车卸煤沟", sampling_method: "机械采样",
    sample_count: 32, sampler: "张三", sampling_date: "2025-05-12"
});
CREATE (sam3:SamplingRecord {
    id: "SAM_003", batch_id: "BATCH_003", sampling_point: "火车卸煤沟", sampling_method: "机械采样",
    sample_count: 49, sampler: "李四", sampling_date: "2025-05-08"
});
CREATE (sam4:SamplingRecord {
    id: "SAM_004", batch_id: "BATCH_004", sampling_point: "火车卸煤沟", sampling_method: "机械采样",
    sample_count: 44, sampler: "李四", sampling_date: "2025-05-15"
});
CREATE (sam5:SamplingRecord {
    id: "SAM_005", batch_id: "BATCH_005", sampling_point: "汽车卸煤沟", sampling_method: "机械采样",
    sample_count: 38, sampler: "王五", sampling_date: "2025-05-05"
});
CREATE (sam6:SamplingRecord {
    id: "SAM_006", batch_id: "BATCH_006", sampling_point: "汽车卸煤沟", sampling_method: "人工采样",
    sample_count: 10, sampler: "赵六", sampling_date: "2025-05-14"
});

/* ==================== 4. 创建制样记录 ==================== */
CREATE (prep1:SamplePreparation {id: "PREP_001", sampling_id: "SAM_001", preparation_method: "破碎-缩分", preparer: "钱七", preparation_date: "2025-05-10"});
CREATE (prep2:SamplePreparation {id: "PREP_002", sampling_id: "SAM_002", preparation_method: "破碎-缩分", preparer: "钱七", preparation_date: "2025-05-12"});
CREATE (prep3:SamplePreparation {id: "PREP_003", sampling_id: "SAM_003", preparation_method: "破碎-缩分", preparer: "孙八", preparation_date: "2025-05-08"});
CREATE (prep4:SamplePreparation {id: "PREP_004", sampling_id: "SAM_004", preparation_method: "破碎-缩分", preparer: "孙八", preparation_date: "2025-05-15"});
CREATE (prep5:SamplePreparation {id: "PREP_005", sampling_id: "SAM_005", preparation_method: "破碎-缩分", preparer: "周九", preparation_date: "2025-05-05"});
CREATE (prep6:SamplePreparation {id: "PREP_006", sampling_id: "SAM_006", preparation_method: "破碎-缩分", preparer: "吴十", preparation_date: "2025-05-14"});

/* ==================== 5. 创建化验结果 ==================== */
CREATE (lab1:LabResult {
    id: "LAB_001", preparation_id: "PREP_001", 
    heat: 5180, sulfur: 0.58, ash: 12.5, volatile_matter: 28.5, moisture: 8.2,
    analyst: "郑一", analysis_date: "2025-05-11", is_qualified: true
});
CREATE (lab2:LabResult {
    id: "LAB_002", preparation_id: "PREP_002",
    heat: 5220, sulfur: 0.54, ash: 12.1, volatile_matter: 28.8, moisture: 8.0,
    analyst: "郑一", analysis_date: "2025-05-13", is_qualified: true
});
CREATE (lab3:LabResult {
    id: "LAB_003", preparation_id: "PREP_003",
    heat: 4750, sulfur: 0.98, ash: 18.2, volatile_matter: 31.5, moisture: 10.2,
    analyst: "王二", analysis_date: "2025-05-09", is_qualified: false
});
CREATE (lab4:LabResult {
    id: "LAB_004", preparation_id: "PREP_004",
    heat: 5480, sulfur: 0.70, ash: 14.0, volatile_matter: 29.0, moisture: 9.0,
    analyst: "王二", analysis_date: "2025-05-16", is_qualified: true
});
CREATE (lab5:LabResult {
    id: "LAB_005", preparation_id: "PREP_005",
    heat: 5750, sulfur: 0.45, ash: 10.5, volatile_matter: 32.0, moisture: 7.5,
    analyst: "李三", analysis_date: "2025-05-06", is_qualified: true
});
CREATE (lab6:LabResult {
    id: "LAB_006", preparation_id: "PREP_006",
    heat: 4100, sulfur: 1.35, ash: 25.0, volatile_matter: 25.0, moisture: 12.0,
    analyst: "李三", analysis_date: "2025-05-15", is_qualified: false
});

/* ==================== 6. 创建煤堆 ==================== */
CREATE (p1:StockPile {
    id: "pile_A", name: "东区1号垛", location: "东区", 
    created_time: "2025-05-10", last_updated: "2025-05-18",
    current_temp: 38, max_temp_history: 42, alert_level: "normal",
    remain: 5000, heat: 5200, sulfur: 0.55, cost: 680
});
CREATE (p2:StockPile {
    id: "pile_B", name: "东区2号垛", location: "东区",
    created_time: "2025-05-05", last_updated: "2025-05-18",
    current_temp: 45, max_temp_history: 52, alert_level: "normal",
    remain: 3200, heat: 5800, sulfur: 0.42, cost: 750
});
CREATE (p3:StockPile {
    id: "pile_C", name: "西区煤棚", location: "西区",
    created_time: "2025-05-08", last_updated: "2025-05-18",
    current_temp: 62, max_temp_history: 65, alert_level: "warning",
    remain: 8000, heat: 4800, sulfur: 0.95, cost: 590
});
CREATE (p4:StockPile {
    id: "pile_D", name: "西区露天", location: "西区",
    created_time: "2025-05-15", last_updated: "2025-05-18",
    current_temp: 35, max_temp_history: 38, alert_level: "normal",
    remain: 4500, heat: 5500, sulfur: 0.68, cost: 650
});

/* ==================== 7. 创建温度监测点 ==================== */
CREATE (temp1:TempMonitorPoint {id: "TEMP_01", pile_id: "pile_C", location: "表层-南侧", realtime_temp: 62, history_temps: "[58,60,61,62,62]"});
CREATE (temp2:TempMonitorPoint {id: "TEMP_02", pile_id: "pile_C", location: "内部-中心", realtime_temp: 58, history_temps: "[55,56,57,58,58]"});
CREATE (temp3:TempMonitorPoint {id: "TEMP_03", pile_id: "pile_B", location: "表层", realtime_temp: 45, history_temps: "[42,43,44,45,45]"});

/* ==================== 8. 创建锅炉 ==================== */
CREATE (boiler1:Boiler {
    id: "BOILER_01", type: "超临界", rated_load: 600, design_coal: "优混煤",
    min_heat: 5000, max_sulfur: 0.7, min_volatile: 25, max_ash: 20
});

/* ==================== 9. 创建约束 ==================== */
CREATE (con1:Constraint {id: "CON_MIN_HEAT", name: "入炉热值下限", value: 5000, unit: "kcal/kg"});
CREATE (con2:Constraint {id: "CON_MAX_SULFUR", name: "入炉硫分上限", value: 0.7, unit: "%"});
CREATE (con3:Constraint {id: "CON_MAX_ASH", name: "入炉灰分上限", value: 20, unit: "%"});
CREATE (con4:Constraint {id: "CON_MIN_VOLATILE", name: "挥发分下限", value: 25, unit: "%"});

/* ==================== 10. 创建所有关系 ==================== */

/* 10.1 供应商-批次关系（新增） */
MATCH (s:Supplier {id: "sup_001"}), (b:CoalBatch {batch_id: "BATCH_001"}) CREATE (s)-[:SUPPLIES]->(b);
MATCH (s:Supplier {id: "sup_001"}), (b:CoalBatch {batch_id: "BATCH_002"}) CREATE (s)-[:SUPPLIES]->(b);
MATCH (s:Supplier {id: "sup_002"}), (b:CoalBatch {batch_id: "BATCH_003"}) CREATE (s)-[:SUPPLIES]->(b);
MATCH (s:Supplier {id: "sup_002"}), (b:CoalBatch {batch_id: "BATCH_004"}) CREATE (s)-[:SUPPLIES]->(b);
MATCH (s:Supplier {id: "sup_003"}), (b:CoalBatch {batch_id: "BATCH_005"}) CREATE (s)-[:SUPPLIES]->(b);
MATCH (s:Supplier {id: "sup_004"}), (b:CoalBatch {batch_id: "BATCH_006"}) CREATE (s)-[:SUPPLIES]->(b);

/* 10.2 批次-采样关系 */
MATCH (b:CoalBatch {batch_id:"BATCH_001"}), (s:SamplingRecord {id:"SAM_001"}) CREATE (b)-[:PRODUCES]->(s);
MATCH (b:CoalBatch {batch_id:"BATCH_002"}), (s:SamplingRecord {id:"SAM_002"}) CREATE (b)-[:PRODUCES]->(s);
MATCH (b:CoalBatch {batch_id:"BATCH_003"}), (s:SamplingRecord {id:"SAM_003"}) CREATE (b)-[:PRODUCES]->(s);
MATCH (b:CoalBatch {batch_id:"BATCH_004"}), (s:SamplingRecord {id:"SAM_004"}) CREATE (b)-[:PRODUCES]->(s);
MATCH (b:CoalBatch {batch_id:"BATCH_005"}), (s:SamplingRecord {id:"SAM_005"}) CREATE (b)-[:PRODUCES]->(s);
MATCH (b:CoalBatch {batch_id:"BATCH_006"}), (s:SamplingRecord {id:"SAM_006"}) CREATE (b)-[:PRODUCES]->(s);

/* 10.3 采样-制样关系 */
MATCH (s:SamplingRecord {id:"SAM_001"}), (p:SamplePreparation {id:"PREP_001"}) CREATE (s)-[:PREPARED_TO]->(p);
MATCH (s:SamplingRecord {id:"SAM_002"}), (p:SamplePreparation {id:"PREP_002"}) CREATE (s)-[:PREPARED_TO]->(p);
MATCH (s:SamplingRecord {id:"SAM_003"}), (p:SamplePreparation {id:"PREP_003"}) CREATE (s)-[:PREPARED_TO]->(p);
MATCH (s:SamplingRecord {id:"SAM_004"}), (p:SamplePreparation {id:"PREP_004"}) CREATE (s)-[:PREPARED_TO]->(p);
MATCH (s:SamplingRecord {id:"SAM_005"}), (p:SamplePreparation {id:"PREP_005"}) CREATE (s)-[:PREPARED_TO]->(p);
MATCH (s:SamplingRecord {id:"SAM_006"}), (p:SamplePreparation {id:"PREP_006"}) CREATE (s)-[:PREPARED_TO]->(p);

/* 10.4 制样-化验关系 */
MATCH (p:SamplePreparation {id:"PREP_001"}), (l:LabResult {id:"LAB_001"}) CREATE (p)-[:TESTED_BY]->(l);
MATCH (p:SamplePreparation {id:"PREP_002"}), (l:LabResult {id:"LAB_002"}) CREATE (p)-[:TESTED_BY]->(l);
MATCH (p:SamplePreparation {id:"PREP_003"}), (l:LabResult {id:"LAB_003"}) CREATE (p)-[:TESTED_BY]->(l);
MATCH (p:SamplePreparation {id:"PREP_004"}), (l:LabResult {id:"LAB_004"}) CREATE (p)-[:TESTED_BY]->(l);
MATCH (p:SamplePreparation {id:"PREP_005"}), (l:LabResult {id:"LAB_005"}) CREATE (p)-[:TESTED_BY]->(l);
MATCH (p:SamplePreparation {id:"PREP_006"}), (l:LabResult {id:"LAB_006"}) CREATE (p)-[:TESTED_BY]->(l);

/* 10.5 批次-煤堆关系（存储） */
MATCH (b:CoalBatch {batch_id:"BATCH_001"}), (p:StockPile {id:"pile_A"}) CREATE (b)-[:STORED_AT]->(p);
MATCH (b:CoalBatch {batch_id:"BATCH_002"}), (p:StockPile {id:"pile_A"}) CREATE (b)-[:STORED_AT]->(p);
MATCH (b:CoalBatch {batch_id:"BATCH_003"}), (p:StockPile {id:"pile_C"}) CREATE (b)-[:STORED_AT]->(p);
MATCH (b:CoalBatch {batch_id:"BATCH_004"}), (p:StockPile {id:"pile_D"}) CREATE (b)-[:STORED_AT]->(p);
MATCH (b:CoalBatch {batch_id:"BATCH_005"}), (p:StockPile {id:"pile_B"}) CREATE (b)-[:STORED_AT]->(p);
MATCH (b:CoalBatch {batch_id:"BATCH_006"}), (p:StockPile {id:"pile_C"}) CREATE (b)-[:STORED_AT]->(p);

/* 10.6 煤堆-温度监测关系 */
MATCH (p:StockPile {id:"pile_C"}), (t:TempMonitorPoint {id:"TEMP_01"}) CREATE (p)-[:MONITORED_BY]->(t);
MATCH (p:StockPile {id:"pile_C"}), (t:TempMonitorPoint {id:"TEMP_02"}) CREATE (p)-[:MONITORED_BY]->(t);
MATCH (p:StockPile {id:"pile_B"}), (t:TempMonitorPoint {id:"TEMP_03"}) CREATE (p)-[:MONITORED_BY]->(t);

/* 10.7 锅炉-约束关系 */
MATCH (bo:Boiler {id:"BOILER_01"}), (c:Constraint {id:"CON_MIN_HEAT"}) CREATE (bo)-[:REQUIRES]->(c);
MATCH (bo:Boiler {id:"BOILER_01"}), (c:Constraint {id:"CON_MAX_SULFUR"}) CREATE (bo)-[:REQUIRES]->(c);
MATCH (bo:Boiler {id:"BOILER_01"}), (c:Constraint {id:"CON_MAX_ASH"}) CREATE (bo)-[:REQUIRES]->(c);
MATCH (bo:Boiler {id:"BOILER_01"}), (c:Constraint {id:"CON_MIN_VOLATILE"}) CREATE (bo)-[:REQUIRES]->(c);

/* 10.8 化验结果与约束的违反关系（扩展） */
MATCH (l:LabResult {id:"LAB_003"}), (c:Constraint {id:"CON_MAX_SULFUR"}) CREATE (l)-[:VIOLATES]->(c);
MATCH (l:LabResult {id:"LAB_006"}), (c:Constraint {id:"CON_MIN_HEAT"}) CREATE (l)-[:VIOLATES]->(c);
MATCH (l:LabResult {id:"LAB_006"}), (c:Constraint {id:"CON_MAX_SULFUR"}) CREATE (l)-[:VIOLATES]->(c);
/* 添加LAB_006违反灰分约束 */
MATCH (l:LabResult {id:"LAB_006"}), (c:Constraint {id:"CON_MAX_ASH"}) CREATE (l)-[:VIOLATES]->(c);
/* 添加LAB_003违反热值约束 */
MATCH (l:LabResult {id:"LAB_003"}), (c:Constraint {id:"CON_MIN_HEAT"}) CREATE (l)-[:VIOLATES]->(c);

/* 10.9 煤堆与风险的关联（新增） */
MATCH (p:StockPile {id:"pile_C"}), (r:Risk {id:"RISK_SPONTANEOUS"}) CREATE (p)-[:HAS_RISK]->(r);
/* 高风险煤堆关联到质量风险 */
MATCH (p:StockPile {id:"pile_C"}), (r:Risk {id:"RISK_QUALITY"}) CREATE (p)-[:HAS_RISK]->(r);
MATCH (p:StockPile {id:"pile_D"}), (r:Risk {id:"RISK_QUALITY"}) CREATE (p)-[:HAS_RISK]->(r);

/* 10.10 化验结果与风险的关联（新增） */
MATCH (l:LabResult {id:"LAB_003"}), (r:Risk {id:"RISK_QUALITY"}) CREATE (l)-[:INDICATES]->(r);
MATCH (l:LabResult {id:"LAB_006"}), (r:Risk {id:"RISK_QUALITY"}) CREATE (l)-[:INDICATES]->(r);

/* 10.11 煤堆与条件的关联（新增） */
MATCH (p:StockPile {id:"pile_C"}), (c:CauseCondition {id:"COND_TEMP_HIGH"}) CREATE (p)-[:SATISFIES]->(c);
MATCH (p:StockPile {id:"pile_C"}), (c:CauseCondition {id:"COND_VOLATILE_HIGH"}) CREATE (p)-[:SATISFIES]->(c);
MATCH (p:StockPile {id:"pile_B"}), (c:CauseCondition {id:"COND_VOLATILE_HIGH"}) CREATE (p)-[:SATISFIES]->(c);

/* ==================== 11. 创建之前的掺配方案记录 ==================== */
CREATE (blend1:BlendPlan {
    id: "BLEND_001", created_at: "2025-05-16", blend_ratio: '{"东区1号垛":60,"西区露天":40}',
    total_cost: 668, blended_heat: 5320, blended_sulfur: 0.60
});
CREATE (blend2:BlendPlan {
    id: "BLEND_002", created_at: "2025-05-17", blend_ratio: '{"东区2号垛":70,"西区煤棚":30}',
    total_cost: 702, blended_heat: 5500, blended_sulfur: 0.58
});

/* 11.1 掺配方案-锅炉关系 */
MATCH (bl:BlendPlan {id:"BLEND_001"}), (bo:Boiler {id:"BOILER_01"}) CREATE (bl)-[:FED_TO]->(bo);
MATCH (bl:BlendPlan {id:"BLEND_002"}), (bo:Boiler {id:"BOILER_01"}) CREATE (bl)-[:FED_TO]->(bo);

/* 11.2 掺配方案与煤堆的关联（新增） */
MATCH (bl:BlendPlan {id:"BLEND_001"}), (p:StockPile {id:"pile_A"}) CREATE (bl)-[:USES]->(p);
MATCH (bl:BlendPlan {id:"BLEND_001"}), (p:StockPile {id:"pile_D"}) CREATE (bl)-[:USES]->(p);
MATCH (bl:BlendPlan {id:"BLEND_002"}), (p:StockPile {id:"pile_B"}) CREATE (bl)-[:USES]->(p);
MATCH (bl:BlendPlan {id:"BLEND_002"}), (p:StockPile {id:"pile_C"}) CREATE (bl)-[:USES]->(p);

/* 11.3 掺配方案-入炉记录 */
CREATE (furnace1:FurnaceRecord {
    id: "FURNACE_001", timestamp: "2025-05-16 08:00:00", 
    actual_heat: 5280, actual_sulfur: 0.62, actual_cost: 670
});
CREATE (furnace2:FurnaceRecord {
    id: "FURNACE_002", timestamp: "2025-05-17 08:00:00",
    actual_heat: 5480, actual_sulfur: 0.59, actual_cost: 705
});

MATCH (bl:BlendPlan {id:"BLEND_001"}), (f:FurnaceRecord {id:"FURNACE_001"}) CREATE (bl)-[:RECORDED_AS]->(f);
MATCH (bl:BlendPlan {id:"BLEND_002"}), (f:FurnaceRecord {id:"FURNACE_002"}) CREATE (bl)-[:RECORDED_AS]->(f);

/* ==================== 12. 创建因果关系（用于推理） ==================== */
CREATE (risk1:Risk {id: "RISK_SPONTANEOUS", name: "自燃风险", level: "warning"});
CREATE (risk2:Risk {id: "RISK_QUALITY", name: "煤质超标风险", level: "alert"});

/* 条件 -> 风险 */
CREATE (c1:CauseCondition {id: "COND_TEMP_HIGH", description: "煤堆温度>60°C"});
CREATE (c2:CauseCondition {id: "COND_VOLATILE_HIGH", description: "挥发分>30%"});
CREATE (c3:CauseCondition {id: "COND_STOCK_TIME", description: "堆放时间>90天"});

MATCH (c:CauseCondition {id:"COND_TEMP_HIGH"}), (r:Risk {id:"RISK_SPONTANEOUS"}) CREATE (c)-[:LEADS_TO]->(r);
MATCH (c:CauseCondition {id:"COND_VOLATILE_HIGH"}), (r:Risk {id:"RISK_SPONTANEOUS"}) CREATE (c)-[:LEADS_TO]->(r);
MATCH (c:CauseCondition {id:"COND_STOCK_TIME"}), (r:Risk {id:"RISK_SPONTANEOUS"}) CREATE (c)-[:LEADS_TO]->(r);

/* ==================== 13. 验证和统计 ==================== */
/* 统计所有节点 */
MATCH (n) RETURN count(n) as total_nodes;

/* 统计所有关系 */
MATCH ()-[r]->() RETURN count(r) as total_relationships;

/* 检查孤立节点（应该为0） */
MATCH (n) WHERE NOT (n)--() RETURN n.id as isolated_nodes;