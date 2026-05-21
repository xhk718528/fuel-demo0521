/* ===== 燃料管理系统 - 仪表板JS ===== */

const API = '';

/* ---- 图表初始化 ---- */
let chartInventory = null;
let chartTemps = null;

function initCharts() {
    if (typeof echarts === 'undefined') return;

    const invEl = document.getElementById('chart-inventory');
    const tmpEl = document.getElementById('chart-temps');

    if (invEl) chartInventory = echarts.init(invEl);
    if (tmpEl) chartTemps = echarts.init(tmpEl);

    window.addEventListener('resize', () => {
        if (chartInventory) chartInventory.resize();
        if (chartTemps) chartTemps.resize();
    });
}

function renderInventoryChart(piles) {
    if (!chartInventory || !piles.length) return;

    const names = piles.map(p => p.name);
    const tonnage = piles.map(p => p.remain || 0);
    const heat = piles.map(p => p.heat || 0);

    chartInventory.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { data: ['库存(吨)', '热值(kcal/kg)'], bottom: 0 },
        grid: { left: 60, right: 60, top: 20, bottom: 40 },
        xAxis: { type: 'value', name: '库存(吨)', nameLocation: 'middle' },
        yAxis: {
            type: 'category',
            data: names,
            axisLabel: { fontSize: 12 }
        },
        series: [
            {
                name: '库存(吨)',
                type: 'bar',
                data: tonnage,
                itemStyle: { color: '#1a73e8', borderRadius: [0, 4, 4, 0] },
                label: { show: true, position: 'right', formatter: '{c} 吨' }
            },
            {
                name: '热值(kcal/kg)',
                type: 'bar',
                data: heat,
                itemStyle: { color: '#34a853', borderRadius: [0, 4, 4, 0] },
                label: { show: true, position: 'right', formatter: '{c}' }
            }
        ]
    });
}

function renderTempsChart(piles) {
    if (!chartTemps || !piles.length) return;

    const names = piles.map(p => p.name);
    const temps = piles.map(p => p.current_temp || 0);
    const sulfur = piles.map(p => p.sulfur || 0);

    chartTemps.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { data: ['温度(°C)', '硫分(%)'], bottom: 0 },
        grid: { left: 60, right: 60, top: 20, bottom: 40 },
        xAxis: { type: 'category', data: names, axisLabel: { fontSize: 11 } },
        yAxis: [
            { type: 'value', name: '温度(°C)', nameLocation: 'middle' },
            { type: 'value', name: '硫分(%)', nameLocation: 'middle', min: 0, max: 1.5 }
        ],
        series: [
            {
                name: '温度(°C)',
                type: 'bar',
                data: temps,
                itemStyle: {
                    color: (params) => {
                        const v = params.value;
                        return v > 60 ? '#ea4335' : v > 50 ? '#fbbc04' : '#1a73e8';
                    }
                },
                label: { show: true, position: 'top', formatter: '{c}°C' }
            },
            {
                name: '硫分(%)',
                type: 'line',
                yAxisIndex: 1,
                data: sulfur.map(v => +v.toFixed(2)),
                itemStyle: { color: '#fbbc04' },
                lineStyle: { width: 3 },
                symbol: 'circle',
                symbolSize: 10,
                label: { show: true, position: 'top', formatter: '{c}%' }
            }
        ]
    });
}

/* ---- 数字滚动动画 ---- */
function animateNumber(el, target, duration, formatter) {
    const start = parseInt(el.textContent) || 0;
    const diff = target - start;
    const startTime = performance.now();

    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        const current = Math.round(start + diff * eased);
        el.textContent = formatter ? formatter(current) : current.toLocaleString();
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

/* ---- 显示/隐藏骨架屏 ---- */
function revealKPI(skelId, kpiId, value, formatter) {
    const skel = document.getElementById(skelId);
    const kpi = document.getElementById(kpiId);
    if (skel) skel.style.display = 'none';
    kpi.style.display = '';
    animateNumber(kpi, value, 600, formatter);
}

/* ---- 标签切换 ---- */
document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        const panel = document.getElementById('panel-' + tab.dataset.tab);
        if (panel) panel.classList.add('active');
        // Load data for the tab
        loadTabData(tab.dataset.tab);
    });
});

function loadTabData(tab) {
    // Reset KPI skeletons when switching away, so they animate again on return
    if (tab !== 'dashboard') {
        ['kpi-piles-skel', 'kpi-tonnage-skel', 'kpi-heat-skel', 'kpi-alerts-skel'].forEach(id => {
            const skel = document.getElementById(id);
            if (skel) skel.style.display = '';
        });
        ['kpi-piles', 'kpi-tonnage', 'kpi-heat', 'kpi-alerts'].forEach(id => {
            const kpi = document.getElementById(id);
            if (kpi) { kpi.style.display = 'none'; kpi.textContent = '0'; }
        });
    }

    switch (tab) {
        case 'dashboard': loadDashboard(); break;
        case 'inventory': loadInventory(); break;
        case 'batches': loadBatches(); break;
        case 'blending': loadBlendHistory(); break;
        case 'alerts': loadAlerts(); break;
        case 'graph': loadGraphData(); break;
    }
}

/* ---- 健康检查 ---- */
async function checkHealth() {
    try {
        const res = await fetch(API + '/health');
        const data = await res.json();
        const dot = document.getElementById('healthDot');
        const text = document.getElementById('healthText');
        dot.className = 'health-dot connected';
        text.textContent = data.status === 'ok' ? `系统正常 | ${data.tools_loaded} 工具` : data.status;
    } catch (e) {
        document.getElementById('healthDot').className = 'health-dot error';
        document.getElementById('healthText').textContent = '连接失败';
    }
}

/* ---- Toast ---- */
function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 3000);
}

/* ---- 弹窗 ---- */
function closeModal(id) { document.getElementById(id).style.display = 'none'; }
function showAddPileModal() { document.getElementById('addPileModal').style.display = 'flex'; }
function showAddBatchModal() { document.getElementById('addBatchModal').style.display = 'flex'; }

/* ---- API 封装 ---- */
async function apiGet(path) {
    const res = await fetch(API + path);
    return res.json();
}

async function apiPost(path, body) {
    const res = await fetch(API + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    return res.json();
}

/* ========== 总览 ========== */
async function loadDashboard() {
    try {
        const status = await apiGet('/fuel/status');
        const risk = await apiGet('/fuel/risk');
        const piles = status.piles || [];

        // KPI - 骨架屏 + 数字滚动
        const totalTonnage = piles.reduce((s, p) => s + (p.remain || 0), 0);

        let avgHeat = 0;
        if (totalTonnage > 0) {
            avgHeat = Math.round(piles.reduce((s, p) => s + (p.heat || 0) * (p.remain || 0), 0) / totalTonnage);
        }

        // Alerts count
        let alertCount = 0;
        piles.forEach(p => { if (p.alert_level === 'warning') alertCount++; });
        (risk.self_ignition || []).forEach(() => alertCount++);
        (risk.unqualified || []).forEach(() => alertCount++);

        revealKPI('kpi-piles-skel', 'kpi-piles', piles.length, v => v);
        revealKPI('kpi-tonnage-skel', 'kpi-tonnage', totalTonnage);
        revealKPI('kpi-heat-skel', 'kpi-heat', avgHeat, v => v);
        revealKPI('kpi-alerts-skel', 'kpi-alerts', alertCount, v => v);

        // Render charts
        renderInventoryChart(piles);
        renderTempsChart(piles);

        // Pile table
        const pileBody = document.getElementById('dash-pile-body');
        pileBody.innerHTML = piles.map(p => `<tr>
            <td>${p.name}</td>
            <td>${p.location}</td>
            <td>${(p.remain||0).toLocaleString()}</td>
            <td>${p.heat}</td>
            <td>${p.sulfur}</td>
            <td>${p.current_temp}</td>
            <td><span class="badge ${p.alert_level==='warning'?'badge-danger':'badge-success'}">${p.alert_level==='warning'?'预警':'正常'}</span></td>
        </tr>`).join('');

        // Blend history
        try {
            const bh = await apiGet('/fuel/blend_history');
            const blendBody = document.getElementById('dash-blend-body');
            const plans = bh.plans || [];
            if (plans.length === 0) {
                blendBody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-secondary)">暂无掺配方案</td></tr>';
            } else {
                blendBody.innerHTML = plans.map(p => {
                    let ratioStr = '--';
                    if (p.blend_ratio) {
                        const ratio = typeof p.blend_ratio === 'string' ? JSON.parse(p.blend_ratio) : p.blend_ratio;
                        ratioStr = Object.entries(ratio).map(([k,v]) => `${k}:${v}%`).join(', ');
                    }
                    return `<tr><td>${p.id}</td><td>${(p.created_at||'').split('.')[0]}</td><td>${ratioStr}</td><td>${p.blended_heat}</td><td>${p.blended_sulfur}</td><td>${p.total_cost}</td></tr>`;
                }).join('');
            }
        } catch (e) {
            console.warn('blend history error:', e);
        }

        // Suppliers from API
        const supDiv = document.getElementById('dash-suppliers');
        const suppliers = status.suppliers || [];
        if (suppliers.length === 0) {
            supDiv.innerHTML = '<div style="text-align:center;color:var(--text-secondary)">暂无供应商数据</div>';
        } else {
            supDiv.innerHTML = suppliers.map(s => `
                <div class="supplier-card">
                    <div class="name">${s.name || s.id}</div>
                    <div class="credit">信用等级: ${s.credit_rating || 'N/A'}</div>
                </div>
            `).join('');
        }

        showToast('总览数据已加载');
    } catch (e) {
        showToast('加载失败: ' + e.message);
    }
}

/* ========== 库存管理 ========== */
async function loadInventory() {
    try {
        const status = await apiGet('/fuel/status');
        const piles = status.piles || [];
        const body = document.getElementById('inventory-body');
        body.innerHTML = piles.map(p => `<tr>
            <td>${p.id}</td>
            <td>${p.name}</td>
            <td>${p.location}</td>
            <td>${(p.remain||0).toLocaleString()}</td>
            <td>${p.heat}</td>
            <td>${p.sulfur}</td>
            <td>${p.cost}</td>
            <td style="color:${p.current_temp>55?'var(--danger)':'inherit'}">${p.current_temp}</td>
            <td>${p.max_temp_history||'--'}</td>
            <td><span class="badge ${p.alert_level==='warning'?'badge-danger':'badge-success'}">${p.alert_level==='warning'?'预警':'正常'}</span></td>
            <td>
                <button class="btn btn-sm" onclick="showPileDetail('${p.id}')">详情</button>
            </td>
        </tr>`).join('');
    } catch (e) {
        showToast('加载失败: ' + e.message);
    }
}

async function showPileDetail(id) {
    try {
        const status = await apiGet('/fuel/status');
        const pile = (status.piles || []).find(p => p.id === id);
        if (!pile) return;
        
        document.getElementById('detailTitle').textContent = `煤堆详情: ${pile.name}`;
        document.getElementById('detailContent').innerHTML = `
            <div class="grid-2" style="gap:12px">
                <div><b>ID:</b> ${pile.id}</div>
                <div><b>名称:</b> ${pile.name}</div>
                <div><b>位置:</b> ${pile.location}</div>
                <div><b>库存:</b> ${(pile.remain||0).toLocaleString()} 吨</div>
                <div><b>热值:</b> ${pile.heat} kcal/kg</div>
                <div><b>硫分:</b> ${pile.sulfur} %</div>
                <div><b>成本:</b> ${pile.cost} 元/吨</div>
                <div><b>当前温度:</b> <span style="color:${pile.current_temp>55?'var(--danger)':'inherit'}">${pile.current_temp} °C</span></div>
                <div><b>最高温度:</b> ${pile.max_temp_history||'--'} °C</div>
                <div><b>预警级别:</b> <span class="badge ${pile.alert_level==='warning'?'badge-danger':'badge-success'}">${pile.alert_level==='warning'?'预警':'正常'}</span></div>
            </div>
        `;
        document.getElementById('detailModal').style.display = 'flex';
    } catch (e) {
        showToast('加载失败: ' + e.message);
    }
}

async function addPile() {
    const data = {
        name: document.getElementById('pile-name').value,
        heat: parseFloat(document.getElementById('pile-heat').value),
        sulfur: parseFloat(document.getElementById('pile-sulfur').value),
        cost: parseFloat(document.getElementById('pile-cost').value),
        remain: parseFloat(document.getElementById('pile-remain').value)
    };
    if (!data.name || isNaN(data.heat) || isNaN(data.sulfur) || isNaN(data.cost) || isNaN(data.remain)) {
        showToast('请填写所有字段');
        return;
    }
    try {
        const res = await apiPost('/fuel/pile', data);
        if (res.status === 'ok') {
            showToast('煤堆添加成功: ' + res.pile_id);
            closeModal('addPileModal');
            loadInventory();
        } else {
            showToast('添加失败: ' + (res.message || '未知错误'));
        }
    } catch (e) {
        showToast('添加失败: ' + e.message);
    }
}

/* ========== 批次管理 ========== */
async function loadBatches() {
    try {
        const status = await apiGet('/fuel/status');
        const batches = status.batches || [];
        const body = document.getElementById('batches-body');
        body.innerHTML = batches.map(b => {
            const diff = b.lab_heat ? (b.lab_heat - b.heat_declared).toFixed(0) : '--';
            const diffColor = b.lab_heat && Math.abs(b.lab_heat - b.heat_declared) > 100 ? 'color:var(--warning)' : '';
            return `<tr>
                <td>${b.batch_id}</td>
                <td>${b.coal_type}</td>
                <td>${b.supplier_id}</td>
                <td>${b.mine_origin || '--'}</td>
                <td>${b.arrival_date}</td>
                <td>${(b.net_weight||0).toLocaleString()}</td>
                <td>${b.heat_declared}</td>
                <td>${b.lab_heat || '--'}</td>
                <td style="${diffColor}">${diff}</td>
                <td>${b.sulfur_declared}</td>
                <td>${b.lab_sulfur || '--'}</td>
                <td>${b.cost}</td>
                <td><button class="btn btn-sm" onclick="traceBatch('${b.batch_id}')">追溯</button></td>
            </tr>`;
        }).join('');

        // 渲染化验结果表格
        const labResults = status.lab_results || [];
        const labBody = document.getElementById('lab-body');
        if (labResults.length === 0) {
            labBody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-secondary)">暂无化验数据</td></tr>';
        } else {
            labBody.innerHTML = labResults.map(l => `<tr>
                <td>${l.lab_id}</td>
                <td>${l.batch_id}</td>
                <td>${l.heat}</td>
                <td>${l.sulfur}</td>
                <td>${l.ash || '--'}</td>
                <td>${l.volatile_matter || '--'}</td>
                <td>${l.moisture || '--'}</td>
                <td>${l.analyst || '--'}</td>
                <td>${l.analysis_date}</td>
                <td><span class="badge ${l.is_qualified ? 'badge-success' : 'badge-danger'}">${l.is_qualified ? '合格' : '不合格'}</span></td>
            </tr>`).join('');
        }

        showToast('批次数据已加载');
    } catch (e) {
        showToast('加载失败: ' + e.message);
    }
}

async function addBatch() {
    const data = {
        supplier_id: document.getElementById('batch-supplier').value,
        coal_type: document.getElementById('batch-type').value,
        mine_origin: document.getElementById('batch-origin').value,
        arrival_date: document.getElementById('batch-date').value || new Date().toISOString().split('T')[0],
        gross_weight: parseFloat(document.getElementById('batch-gross').value) || 0,
        net_weight: parseFloat(document.getElementById('batch-net').value) || 0,
        heat_declared: parseFloat(document.getElementById('batch-heat').value) || 0,
        sulfur_declared: parseFloat(document.getElementById('batch-sulfur').value) || 0,
        cost: parseFloat(document.getElementById('batch-cost').value) || 0,
        vehicle_count: 0
    };
    if (!data.coal_type || !data.supplier_id) {
        showToast('请填写煤种和供应商');
        return;
    }
    try {
        const res = await apiPost('/fuel/batch', data);
        if (res.status === 'ok') {
            showToast('批次添加成功: ' + res.batch_id);
            closeModal('addBatchModal');
            loadBatches();
        } else {
            showToast('添加失败: ' + (res.message || '未知错误'));
        }
    } catch (e) {
        showToast('添加失败: ' + e.message);
    }
}

function traceBatch(id) {
    document.querySelector('[data-tab="trace"]').click();
    document.getElementById('trace-input').value = id;
    runTrace();
}

/* ========== 掺配优化 ========== */
async function runBlendOptimization() {
    const heat = parseFloat(document.getElementById('blend-heat').value);
    const sulfur = parseFloat(document.getElementById('blend-sulfur').value);
    const resultBox = document.getElementById('blend-result');
    resultBox.style.display = 'block';
    resultBox.innerHTML = '<div class="loading"><span class="spinner"></span> 计算中...</div>';

    try {
        const data = await apiPost('/fuel/optimize', {
            target_heat: heat,
            target_sulfur: sulfur
        });

        if (data.status !== 'ok') {
            resultBox.innerHTML = `<div class="alert-item critical"><span class="alert-icon">&#10060;</span><div class="alert-content"><div class="alert-title">计算失败</div><div class="alert-desc">${data.message}</div></div></div>`;
            return;
        }

        let html = `<div style="margin-bottom:12px">
            <span class="badge badge-success">方案已生成</span>
            <span style="margin-left:8px;font-size:13px;color:var(--text-secondary)">方案ID: ${data.plan_id}</span>
        </div>`;

        // 目标约束
        html += `<div style="font-size:13px;color:var(--text-secondary);margin-bottom:12px">
            目标：热值 ≥ ${data.target_heat} kcal/kg，硫分 ≤ ${data.target_sulfur}%
        </div>`;

        // 混合指标卡片
        html += `<div class="grid-2" style="margin-bottom:16px;gap:8px">
            <div style="background:#e8f0fe;padding:12px;border-radius:8px;text-align:center">
                <div style="font-size:24px;font-weight:700;color:var(--primary)">${data.blended_heat}</div>
                <div style="font-size:12px;color:var(--text-secondary)">混合热值 (kcal/kg)</div>
            </div>
            <div style="background:#fef7e0;padding:12px;border-radius:8px;text-align:center">
                <div style="font-size:24px;font-weight:700;color:#e37400">${data.blended_sulfur}%</div>
                <div style="font-size:12px;color:var(--text-secondary)">混合硫分</div>
            </div>
            <div style="background:#e6f4ea;padding:12px;border-radius:8px;text-align:center">
                <div style="font-size:24px;font-weight:700;color:var(--success)">${data.total_cost}</div>
                <div style="font-size:12px;color:var(--text-secondary)">综合成本 (元/吨)</div>
            </div>
            <div style="background:#f8f9fa;padding:12px;border-radius:8px;text-align:center">
                <div style="font-size:24px;font-weight:700;color:var(--text)">${data.max_batch_tons.toLocaleString()}</div>
                <div style="font-size:12px;color:var(--text-secondary)">最大掺批量 (吨)</div>
            </div>
        </div>`;

        // 掺配明细表格
        html += `<table class="data-table"><thead><tr>
            <th>煤堆名称</th><th>掺配比例</th><th>热值贡献</th><th>硫分贡献</th><th>成本贡献</th><th>可用库存</th>
        </tr></thead><tbody>`;
        for (const d of data.details) {
            html += `<tr>
                <td>${d.pile_name}</td>
                <td><strong>${d.ratio}%</strong></td>
                <td>${d.heat_contribution}</td>
                <td>${d.sulfur_contribution}</td>
                <td>${d.cost_contribution}</td>
                <td>${d.available_tons.toLocaleString()} 吨</td>
            </tr>`;
        }
        html += `</tbody></table>`;

        resultBox.innerHTML = html;

        // 刷新历史列表
        loadBlendHistory();
        showToast('掺配方案已生成');
    } catch (e) {
        resultBox.innerHTML = `<div class="alert-item critical"><span class="alert-icon">&#10060;</span><div class="alert-content"><div class="alert-title">计算失败</div><div class="alert-desc">${e.message}</div></div></div>`;
    }
}

async function loadBlendHistory() {
    try {
        const body = document.getElementById('blend-history-body');
        body.innerHTML = '<tr><td colspan="6" class="loading"><span class="spinner"></span> 加载中...</td></tr>';
        const bh = await apiGet('/fuel/blend_history');
        const plans = bh.plans || [];
        if (plans.length === 0) {
            body.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-secondary)">暂无掺配方案</td></tr>';
        } else {
            body.innerHTML = plans.map(p => {
                let ratioStr = '--';
                if (p.blend_ratio) {
                    const ratio = typeof p.blend_ratio === 'string' ? JSON.parse(p.blend_ratio) : p.blend_ratio;
                    ratioStr = Object.entries(ratio).map(([k,v]) => `${k}:${v}%`).join(', ');
                }
                return `<tr><td>${p.id}</td><td>${(p.created_at||'').split('.')[0]}</td><td>${ratioStr}</td><td>${p.blended_heat}</td><td>${p.blended_sulfur}</td><td>${p.total_cost}</td></tr>`;
            }).join('');
        }
    } catch (e) {
        showToast('加载失败: ' + e.message);
    }
}

/* ========== 预警中心 ========== */
async function loadAlerts() {
    try {
        const risk = await apiGet('/fuel/risk');
        
        // Self-ignition alerts
        const siDiv = document.getElementById('self-ignition-alerts');
        const si = risk.self_ignition || [];
        if (si.length === 0) {
            siDiv.innerHTML = '<div class="alert-item"><span class="alert-icon">&#9989;</span><div class="alert-content"><div class="alert-title">无自燃风险</div><div class="alert-desc">所有煤堆温度正常</div></div></div>';
        } else {
            siDiv.innerHTML = si.map(a => `
                <div class="alert-item critical">
                    <span class="alert-icon">&#128293;</span>
                    <div class="alert-content">
                        <div class="alert-title">${a.pile_name || a.pile_id || '未知煤堆'}</div>
                        <div class="alert-desc">温度: ${a.current_temp || '--'} °C | 建议: 及时翻堆散热</div>
                    </div>
                </div>
            `).join('');
        }
        
        // Quality alerts
        const qDiv = document.getElementById('quality-alerts');
        const uq = risk.unqualified || [];
        if (uq.length === 0) {
            qDiv.innerHTML = '<div class="alert-item"><span class="alert-icon">&#9989;</span><div class="alert-content"><div class="alert-title">无煤质超标</div><div class="alert-desc">所有批次化验合格</div></div></div>';
        } else {
            qDiv.innerHTML = uq.map(a => `
                <div class="alert-item">
                    <span class="alert-icon">&#9888;</span>
                    <div class="alert-content">
                        <div class="alert-title">${a.batch_id || '未知批次'}</div>
                        <div class="alert-desc">热值: ${a.heat} | 硫分: ${a.sulfur} | ${a.violated_constraint || '超标'}</div>
                    </div>
                </div>
            `).join('');
        }
        
        // High risk piles
        const hrBody = document.getElementById('high-risk-body');
        const hr = risk.high_risk || [];
        if (hr.length === 0) {
            hrBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-secondary)">暂无高风险煤堆</td></tr>';
        } else {
            hrBody.innerHTML = hr.map(p => `<tr>
                <td>${p.pile_id}</td>
                <td>${p.name}</td>
                <td style="color:var(--danger)">${p.current_temp}</td>
                <td><span class="badge badge-danger">${p.alert_level}</span></td>
                <td>${(p.remain||0).toLocaleString()}</td>
            </tr>`).join('');
        }
        
        showToast('预警数据已加载');
    } catch (e) {
        showToast('加载失败: ' + e.message);
    }
}

/* ========== 全流程追溯 ========== */
async function runTrace() {
    const batchId = document.getElementById('trace-input').value.trim();
    if (!batchId) { showToast('请输入批次ID'); return; }
    
    const resultDiv = document.getElementById('trace-result');
    resultDiv.innerHTML = '<div class="loading"><span class="spinner"></span> 追溯中...</div>';
    
    try {
        const data = await apiGet(`/fuel/trace/${batchId}`);
        const trace = data.result;
        
        if (!trace || !trace.batch) {
            resultDiv.innerHTML = '<div class="alert-item"><span class="alert-icon">&#10060;</span><div class="alert-content"><div class="alert-title">未找到批次</div><div class="alert-desc">请检查批次ID是否正确</div></div></div>';
            return;
        }
        
        const b = trace.batch;
        let html = `<h4 style="margin-bottom:16px">📋 批次: ${b.batch_id} (${b.coal_type})</h4>`;
        html += '<div class="timeline">';
        
        // Step 1: 入厂
        html += `<div class="timeline-item">
            <div class="tl-title">🏭 入厂接收</div>
            <div class="tl-time">${b.arrival_date || '未知日期'}</div>
            <div class="tl-detail">供应商: ${b.supplier_id} | 矿源: ${b.mine_origin} | 净重: ${(b.net_weight||0).toLocaleString()} 吨 | 申报热值: ${b.heat_declared} | 申报硫分: ${b.sulfur_declared}</div>
        </div>`;
        
        // Step 2: 采样
        (trace.samplings || []).forEach(s => {
            html += `<div class="timeline-item">
                <div class="tl-title">🔬 采样记录</div>
                <div class="tl-time">${s.sampling_date || '未知日期'}</div>
                <div class="tl-detail">采样点: ${s.sampling_point} | 方法: ${s.sampling_method} | 采样员: ${s.sampler} | 样本数: ${s.sample_count}</div>
            </div>`;
        });
        
        // Step 3: 制样
        (trace.preparations || []).forEach(p => {
            html += `<div class="timeline-item">
                <div class="tl-title">🧪 制样处理</div>
                <div class="tl-time">${p.preparation_date || '未知日期'}</div>
                <div class="tl-detail">方法: ${p.preparation_method} | 制样员: ${p.preparer}</div>
            </div>`;
        });
        
        // Step 4: 化验
        (trace.lab_results || []).forEach(l => {
            html += `<div class="timeline-item">
                <div class="tl-title">📊 化验结果 ${l.is_qualified ? '<span class="badge badge-success">合格</span>' : '<span class="badge badge-danger">不合格</span>'}</div>
                <div class="tl-time">${l.analysis_date || '未知日期'}</div>
                <div class="tl-detail">热值: ${l.heat} kcal/kg | 硫分: ${l.sulfur} % | 灰分: ${l.ash} % | 挥发分: ${l.volatile_matter} % | 水分: ${l.moisture} % | 化验员: ${l.analyst}</div>
            </div>`;
        });
        
        // Step 5: 存储
        (trace.stock_piles || []).forEach(p => {
            html += `<div class="timeline-item">
                <div class="tl-title">📦 存储煤堆</div>
                <div class="tl-time">当前库存</div>
                <div class="tl-detail">煤堆: ${p.name} (${p.location}) | 库存: ${(p.remain||0).toLocaleString()} 吨 | 温度: ${p.current_temp} °C | 状态: ${p.alert_level}</div>
            </div>`;
        });
        
        html += '</div>';
        resultDiv.innerHTML = html;
    } catch (e) {
        resultDiv.innerHTML = `<div class="alert-item critical"><span class="alert-icon">&#10060;</span><div class="alert-content"><div class="alert-title">追溯失败</div><div class="alert-desc">${e.message}</div></div></div>`;
    }
}

/* ---- 初始化 ---- */
initCharts();
checkHealth();
loadDashboard();

/* ========== 知识图谱可视化 ========== */

let chartGraph = null;
let graphLabelsVisible = true;
let graphDataCache = null;

// 节点分类颜色
const GRAPH_CATEGORY_COLORS = {
    '供应商': '#1a73e8',
    '煤批次': '#34a853',
    '采样记录': '#fbbc04',
    '制样': '#ff9800',
    '化验结果': '#ea4335',
    '煤堆': '#9c27b0',
    '测温点': '#00bcd4',
    '约束条件': '#607d8b',
    '风险': '#e91e63',
    '掺配方案': '#009688',
    '锅炉': '#795548',
    '原因条件': '#673ab7',
    '入炉记录': '#ff5722',
};

function initGraphChart() {
    if (typeof echarts === 'undefined') return;
    const el = document.getElementById('graph-chart');
    if (!el) return;
    if (chartGraph) chartGraph.dispose();
    chartGraph = echarts.init(el);
    window.addEventListener('resize', () => {
        if (chartGraph) chartGraph.resize();
    });
}

async function loadGraphData() {
    initGraphChart();
    if (!chartGraph) return;

    chartGraph.showLoading({
        text: '加载图谱数据...',
        color: 'var(--primary)',
        textColor: 'var(--text)',
        maskColor: 'rgba(245,247,250,0.8)',
    });

    try {
        const data = await apiGet('/fuel/graph');

        if (data.status !== 'ok') {
            chartGraph.hideLoading();
            showToast('图谱加载失败: ' + (data.message || '未知错误'));
            return;
        }

        graphDataCache = data;
        renderGraph(data);
        chartGraph.hideLoading();

        // Stats
        document.getElementById('graph-stats').textContent =
            `${data.stats.total_nodes} 个节点 / ${data.stats.total_relations} 条关系`;

        showToast('知识图谱已加载');
    } catch (e) {
        chartGraph.hideLoading();
        showToast('加载失败: ' + e.message);
    }
}

function renderGraph(data) {
    const { nodes, links } = data;

    // 提取分类
    const categories = [];
    const catSet = new Set();
    for (const n of nodes) {
        if (!catSet.has(n.category)) {
            catSet.add(n.category);
            categories.push({
                name: n.category,
                itemStyle: {
                    color: GRAPH_CATEGORY_COLORS[n.category] || '#999',
                },
            });
        }
    }

    // 映射节点 category 为索引
    const catIndexMap = {};
    categories.forEach((c, i) => { catIndexMap[c.name] = i; });

    const graphNodes = nodes.map((n, i) => ({
        id: n.id,
        name: n.name,
        symbolSize: getNodeSize(n.category),
        category: catIndexMap[n.category] ?? 0,
        label: {
            show: graphLabelsVisible,
            fontSize: 11,
            formatter: (params) => {
                // 截断过长的名称
                const name = params.name || '';
                return name.length > 20 ? name.substring(0, 18) + '...' : name;
            },
        },
        raw: n, // 保留原始数据用于点击详情
    }));

    const graphLinks = links.map(l => ({
        source: l.source,
        target: l.target,
        name: l.name,
        lineStyle: {
            curveness: 0.2,
            color: 'source',
            width: 1.5,
            opacity: 0.6,
        },
        label: {
            show: false, // 默认隐藏关系标签，太乱
        },
    }));

    const option = {
        tooltip: {
            trigger: 'item',
            formatter: (params) => {
                if (params.dataType === 'node') {
                    return `<b>${params.name}</b><br/>类型: ${params.data.raw?.category || ''}`;
                } else if (params.dataType === 'edge') {
                    return `${params.data.source} --[${params.name}]--> ${params.data.target}`;
                }
                return '';
            },
        },
        legend: {
            show: false, // 用自定义图例
        },
        series: [
            {
                type: 'graph',
                layout: 'force',
                rotationRotation: 0,
                focusNodeAdjacency: true,
                emphasis: {
                    focus: 'adjacency',
                    lineStyle: { width: 3 },
                },
                data: graphNodes,
                links: graphLinks,
                categories: categories,
                roam: true,
                draggable: true,
                force: {
                    repulsion: 300,
                    gravity: 0.1,
                    edgeLength: [80, 200],
                    layoutAnimation: true,
                    friction: 0.6,
                },
                label: {
                    show: graphLabelsVisible,
                    position: 'right',
                    fontSize: 11,
                    color: '#333',
                },
                lineStyle: {
                    color: 'source',
                    curveness: 0.2,
                    width: 1.5,
                    opacity: 0.6,
                },
                edgeLabel: {
                    show: false,
                },
            },
        ],
    };

    chartGraph.setOption(option, true);

    // 点击节点显示详情
    chartGraph.off('click');
    chartGraph.on('click', (params) => {
        if (params.dataType === 'node' && params.data?.raw) {
            showGraphNodeInfo(params.data.raw);
        }
    });

    // 渲染自定义图例
    renderGraphLegend(categories);
}

function getNodeSize(category) {
    const sizes = {
        '供应商': 45,
        '煤堆': 40,
        '煤批次': 35,
        '锅炉': 40,
        '掺配方案': 35,
        '化验结果': 30,
        '采样记录': 25,
        '制样': 25,
        '测温点': 22,
        '约束条件': 25,
        '风险': 30,
        '原因条件': 25,
        '入炉记录': 25,
    };
    return sizes[category] || 28;
}

function showGraphNodeInfo(node) {
    const infoPanel = document.getElementById('graph-node-info');
    const titleEl = document.getElementById('graph-node-title');
    const propsEl = document.getElementById('graph-node-props');

    titleEl.textContent = `${node.category}: ${node.name}`;

    let html = '';
    if (node.props) {
        for (const [key, val] of Object.entries(node.props)) {
            if (val !== null && val !== undefined && val !== '') {
                html += `<div class="prop-row"><span class="prop-key">${key}</span><span class="prop-val">${formatValue(val)}</span></div>`;
            }
        }
    }
    if (!html) html = '<div style="color:var(--text-secondary)">无额外属性</div>';
    propsEl.innerHTML = html;

    infoPanel.style.display = 'block';
}

function formatValue(val) {
    if (typeof val === 'object') return JSON.stringify(val);
    if (typeof val === 'number') {
        if (Number.isInteger(val)) return val.toLocaleString();
        return val.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
    }
    return String(val);
}

function renderGraphLegend(categories) {
    const container = document.getElementById('graph-legend-panel');
    container.innerHTML = categories.map(c => `
        <div class="graph-legend-item">
            <span class="graph-legend-dot" style="background:${c.itemStyle.color}"></span>
            <span>${c.name}</span>
        </div>
    `).join('');
}

function toggleGraphLabels() {
    graphLabelsVisible = !graphLabelsVisible;
    if (chartGraph && graphDataCache) {
        const nodes = graphDataCache.nodes.map(n => ({
            id: n.id,
            label: { show: graphLabelsVisible },
        }));
        chartGraph.setOption({
            series: [{
                data: nodes,
            }],
        });
    }
}

/* ========== AI 聊天气泡 ========== */

const aiChatState = {
    sessionId: 'dashboard_' + (localStorage.getItem('dashboard_chat_sid') || genChatId()),
    messages: JSON.parse(localStorage.getItem('dashboard_chat_msgs') || '[]'),
    isStreaming: false,
};

function genChatId() {
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    localStorage.setItem('dashboard_chat_sid', id);
    return id;
}

function saveChatMessages() {
    localStorage.setItem('dashboard_chat_msgs', JSON.stringify(aiChatState.messages));
}

function renderMarkdown(text) {
    if (window.marked) return window.marked.parse(text);
    return text.split('\n\n').map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

/* ---- 气泡开关 ---- */

const chatBubbleToggle = document.getElementById('chatBubbleToggle');
const aiChatBubble = document.getElementById('aiChatBubble');
const aiChatClose = document.getElementById('aiChatBubbleClose');
const aiChatMessages = document.getElementById('aiChatMessages');
const aiChatInput = document.getElementById('aiChatInput');
const aiChatSendBtn = document.getElementById('aiChatSendBtn');
const aiChatStatusBar = document.getElementById('aiChatStatusBar');
const aiChatStatusText = document.getElementById('aiChatStatusText');
const aiChatWelcome = document.getElementById('aiChatWelcome');

chatBubbleToggle.addEventListener('click', () => {
    const shown = aiChatBubble.style.display !== 'none';
    if (shown) {
        aiChatBubble.style.display = 'none';
    } else {
        aiChatBubble.style.display = 'flex';
        renderChatHistory();
        aiChatInput.focus();
    }
});

aiChatClose.addEventListener('click', () => {
    aiChatBubble.style.display = 'none';
});

/* ---- 渲染历史 ---- */

function renderChatHistory() {
    aiChatMessages.innerHTML = '';
    const msgs = aiChatState.messages;
    if (msgs.length === 0) {
        aiChatWelcome.style.display = 'flex';
        return;
    }
    aiChatWelcome.style.display = 'none';
    for (const msg of msgs) {
        if (msg.role === 'user') {
            appendBubbleMessage('user', msg.content);
        } else {
            appendBubbleMessage('assistant', msg.content);
        }
    }
    scrollBubbleBottom();
}

function scrollBubbleBottom() {
    requestAnimationFrame(() => {
        aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
    });
}

/* ---- 气泡消息 ---- */

function appendBubbleMessage(role, content) {
    const el = document.createElement('div');
    el.className = `ai-chat-msg ${role}`;
    const avatar = role === 'user' ? 'Y' : 'AI';
    el.innerHTML = `
        <div class="ai-chat-msg-avatar">${avatar}</div>
        <div class="ai-chat-msg-bubble"><div class="ai-chat-msg-content">${role === 'user' ? escapeHtml(content) : renderMarkdown(content || '')}</div></div>
    `;
    aiChatMessages.appendChild(el);
    scrollBubbleBottom();
    return el.querySelector('.ai-chat-msg-content');
}

function appendBubbleThinking(text) {
    const el = document.createElement('div');
    el.className = 'ai-chat-msg thinking';
    el.innerHTML = `
        <div class="ai-chat-msg-avatar">\u{1F914}</div>
        <div class="ai-chat-msg-bubble"><div class="thinking-content">${escapeHtml(text)}</div></div>
    `;
    aiChatMessages.appendChild(el);
    scrollBubbleBottom();
    return el.querySelector('.thinking-content');
}

function appendBubbleToolCall(name, args, status, result) {
    const argsStr = args ? JSON.stringify(args, null, 2) : '';
    const resultStr = (result !== undefined && result !== null) ? String(result).slice(0, 300) : '';
    let statusBadge = '';
    if (status === 'completed') {
        statusBadge = '<span class="tool-call-status done">\u2713</span>';
    } else if (status === 'error') {
        statusBadge = '<span class="tool-call-status err">\u2717</span>';
    } else {
        statusBadge = '<span class="tool-call-status running">\u27C3</span>';
    }
    let bodyHtml = '';
    if (argsStr) bodyHtml += `<pre class="tool-call-args">${escapeHtml(argsStr)}</pre>`;
    if (resultStr) bodyHtml += `<pre class="tool-call-result">${escapeHtml(resultStr)}</pre>`;
    const el = document.createElement('div');
    el.className = 'ai-chat-msg tool-call';
    el.innerHTML = `
        <div class="ai-chat-msg-avatar">\u{1F527}</div>
        <div class="ai-chat-msg-bubble">
            <div class="tool-call-header">${escapeHtml(name)} ${statusBadge}</div>
            ${bodyHtml}
        </div>
    `;
    aiChatMessages.appendChild(el);
    scrollBubbleBottom();
    return el;
}

function updateBubbleToolCall(el, status, result) {
    const header = el.querySelector('.tool-call-header');
    if (header) {
        const badge = header.querySelector('.tool-call-status');
        if (badge) {
            badge.className = `tool-call-status ${status === 'completed' ? 'done' : 'err'}`;
            badge.textContent = status === 'completed' ? '\u2713' : '\u2717';
        }
    }
    if (result !== undefined) {
        let resultEl = el.querySelector('.tool-call-result');
        if (!resultEl) {
            resultEl = document.createElement('pre');
            resultEl.className = 'tool-call-result';
            el.querySelector('.ai-chat-msg-bubble').appendChild(resultEl);
        }
        resultEl.textContent = String(result).slice(0, 300);
    }
}

function showBubbleStatus(text) {
    aiChatStatusBar.style.display = 'flex';
    aiChatStatusText.textContent = text;
}

function hideBubbleStatus() {
    aiChatStatusBar.style.display = 'none';
}

/* ---- 发送消息 ---- */

function updateBubbleSendBtn() {
    aiChatSendBtn.disabled = !aiChatInput.value.trim() || aiChatState.isStreaming;
}

aiChatInput.addEventListener('input', () => {
    aiChatInput.style.height = 'auto';
    aiChatInput.style.height = Math.min(aiChatInput.scrollHeight, 100) + 'px';
    updateBubbleSendBtn();
});

aiChatInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendBubbleMessage();
    }
});

aiChatSendBtn.addEventListener('click', sendBubbleMessage);

async function sendBubbleMessage() {
    const text = aiChatInput.value.trim();
    if (!text || aiChatState.isStreaming) return;

    aiChatWelcome.style.display = 'none';

    aiChatState.messages.push({ role: 'user', content: text });
    saveChatMessages();
    appendBubbleMessage('user', text);

    aiChatInput.value = '';
    aiChatInput.style.height = 'auto';
    updateBubbleSendBtn();

    aiChatState.isStreaming = true;
    updateBubbleSendBtn();
    showBubbleStatus('思考中...');

    const contentEl = appendBubbleMessage('assistant', '');
    const state = { fullContent: '' };

    try {
        const resp = await fetch('/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                session_id: aiChatState.sessionId,
            }),
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        state.fullContent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('event: ')) continue;
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]' || !data) continue;
                    if (data.startsWith('{')) {
                        try {
                            const evt = JSON.parse(data);
                            handleBubbleEvent(evt, contentEl, state);
                        } catch (e) {
                            // skip
                        }
                    }
                }
            }
        }

        aiChatState.messages.push({ role: 'assistant', content: state.fullContent || '(无回复)' });
        saveChatMessages();
    } catch (err) {
        contentEl.innerHTML = `<span style="color:#FF3B30">错误: ${escapeHtml(err.message)}</span>`;
    } finally {
        aiChatState.isStreaming = false;
        updateBubbleSendBtn();
        hideBubbleStatus();
        aiChatInput.focus();
    }
}

function handleBubbleEvent(evt, contentEl, state) {
    const e = evt.event;
    const d = evt.data || {};

    switch (e) {
        case 'content':
        case 'RunContent': {
            const txt = d.content || '';
            if (txt) {
                state.fullContent += txt;
                contentEl.innerHTML = renderMarkdown(state.fullContent);
                scrollBubbleBottom();
            }
            if (d.reasoning && d.content) {
                showBubbleStatus('思考中...');
            } else if (txt) {
                showBubbleStatus('回复中...');
            }
            break;
        }
        case 'reasoning':
        case 'ReasoningContentDelta':
        case 'ReasoningStep': {
            showBubbleStatus('思考中...');
            break;
        }
        case 'tool_call':
        case 'ToolCallStarted': {
            showBubbleStatus(`调用工具: ${d.tool_name || ''}...`);
            break;
        }
        case 'tool_result':
        case 'ToolCallCompleted':
        case 'ToolCallError': {
            showBubbleStatus('思考中...');
            break;
        }
        case 'run_completed':
        case 'RunCompleted': {
            hideBubbleStatus();
            break;
        }
        case 'error': {
            contentEl.innerHTML = `<span style="color:#FF3B30">错误: ${escapeHtml(d.message || '')}</span>`;
            break;
        }
    }
}
