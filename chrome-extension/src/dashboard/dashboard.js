/**
 * Application Tracker Dashboard - Display and manage applications
 */

import { escapeHtml } from "../utils/sanitize.js";

const API_BASE = "http://localhost:8899/api/v1";

// API 调用辅助函数 — 自动附带 API Key
async function apiCall(method, path, body = null) {
  const { apiKey } = await chrome.storage.local.get("apiKey");
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (apiKey) options.headers["X-API-Key"] = apiKey;
  if (body) options.body = JSON.stringify(body);
  const response = await fetch(`${API_BASE}${path}`, options);
  if (response.status === 401) {
    throw new Error("API 密钥未配置，请先在设置页面填写 API 密钥。");
  }
  return response.json();
}
const positionFilter = document.getElementById("positionFilter");
const companyFilter = document.getElementById("companyFilter");
const statusFilter = document.getElementById("statusFilter");
const tableBody = document.getElementById("tableBody");
const exportBtn = document.getElementById("exportBtn");
const refreshBtn = document.getElementById("refreshBtn");

const PAGE_SIZE = 20;
let currentPage = 1;
let allApplications = [];
let allConnections = [];

// --- Tab Switching ---
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
    if (tab.dataset.tab === "connections") {
      loadConnections();
    }
  });
});

async function loadApplications(page) {
  if (page === undefined) {
    page = currentPage;
  }
  try {
    const data = await apiCall("GET", `/applications?per_page=${PAGE_SIZE}&page=${page}`);
    allApplications = data;
    currentPage = page;
    filterAndRender();
    loadStats();
    updatePagination();
  } catch (error) {
    tableBody.innerHTML =
      '<tr><td colspan="7" class="no-data">加载投递记录失败</td></tr>';
  }
}

function updatePagination() {
  const container = document.getElementById("paginationContainer");
  if (!container) return;
  container.innerHTML = "";

  const prevBtn = document.createElement("button");
  prevBtn.textContent = "上一页";
  prevBtn.disabled = currentPage <= 1;
  prevBtn.addEventListener("click", () => loadApplications(currentPage - 1));

  const pageInfo = document.createElement("span");
  pageInfo.textContent = ` 第 ${currentPage} 页 `;
  pageInfo.style.margin = "0 12px";
  pageInfo.style.lineHeight = "36px";
  pageInfo.style.color = "#333";
  pageInfo.style.fontSize = "13px";

  const nextBtn = document.createElement("button");
  nextBtn.textContent = "下一页";
  nextBtn.disabled = allApplications.length < PAGE_SIZE;
  nextBtn.addEventListener("click", () => loadApplications(currentPage + 1));

  container.appendChild(prevBtn);
  container.appendChild(pageInfo);
  container.appendChild(nextBtn);
}

function filterAndRender() {
  const positionText = positionFilter.value.toLowerCase();
  const companyText = companyFilter.value.toLowerCase();
  const statusText = statusFilter.value;

  const filtered = allApplications.filter((app) => {
    const matchPosition =
      !positionText ||
      (app.job?.title || "").toLowerCase().includes(positionText);
    const matchCompany =
      !companyText ||
      (app.job?.company || "").toLowerCase().includes(companyText);
    const matchStatus = !statusText || app.status === statusText;
    return matchPosition && matchCompany && matchStatus;
  });

  tableBody.innerHTML = "";
  if (filtered.length === 0) {
    tableBody.innerHTML =
      '<tr><td colspan="7" class="no-data">暂无投递记录</td></tr>';
    return;
  }

  filtered.forEach((app) => {
    const row = document.createElement("tr");
    const statusMap = { applied: "已投递", failed: "失败", pending: "待处理", pending_retry: "待重试", dry_run: "模拟" };
    const statusText = statusMap[app.status] || escapeHtml(app.status);
    const statusBadge = `<span class="badge ${escapeHtml(app.status)}">${statusText}</span>`;
    const appliedDate = app.applied_at
      ? new Date(app.applied_at).toLocaleDateString("zh-CN")
      : "-";

    // Match score display
    const score = app.job?.match_score ?? 0;
    const scoreColor = score >= 70 ? "#0a66c2" : score >= 40 ? "#e8a838" : "#dc3545";
    const scoreBadge = `<span style="color:${scoreColor};font-weight:700;">${score}%</span>`;

    row.innerHTML = `
      <td>${escapeHtml(app.job?.title || "未知")}</td>
      <td>${escapeHtml(app.job?.company || "未知")}</td>
      <td>${escapeHtml(app.job?.location || "-")}</td>
      <td>${scoreBadge}</td>
      <td>${appliedDate}</td>
      <td>${statusBadge}</td>
      <td>
        <button class="action-btn" data-action="viewDetails" data-id="${app.id}">详情</button>
      </td>
    `;
    tableBody.appendChild(row);
  });
}

async function loadStats() {
  try {
    // /stats/summary aggregates the last 7 days across the full DB,
    // not just the current page of records, so the totals match reality.
    const summary = await apiCall("GET", "/stats/summary");
    const total = summary?.total_applications ?? 0;
    const successful = summary?.successful ?? 0;
    const failed = summary?.failed ?? 0;
    const pending = Math.max(total - successful - failed, 0);
    const dryRun = allApplications.filter((a) => a.status === "dry_run").length;

    document.getElementById("stats").innerHTML = `
      <div class="stat-card">
        <div class="stat-label">总投递数（近 7 天）</div>
        <div class="stat-value">${escapeHtml(String(successful))}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">失败</div>
        <div class="stat-value">${escapeHtml(String(failed))}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">模拟提交（dry-run）</div>
        <div class="stat-value">${escapeHtml(String(dryRun))}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">待处理 / 其他</div>
        <div class="stat-value">${escapeHtml(String(pending))}</div>
      </div>
      <div class="stat-card" id="chartCard">
        <div class="stat-label">每日投递量（近 7 天）</div>
        <div id="dailyChart"></div>
      </div>
    `;
    // Chart still uses the in-memory page since /stats/summary returns
    // aggregates only; OK as a coarse 7-day shape from recent records.
    renderDailyChart(allApplications);
  } catch (error) {
    console.error("Error loading stats:", error);
  }
}

function renderDailyChart(applications) {
  const container = document.getElementById("dailyChart");
  if (!container) return;

  // Build daily counts for last 7 days
  const dailyCounts = [];
  const now = new Date();
  for (let i = 6; i >= 0; i--) {
    const day = new Date(now);
    day.setDate(day.getDate() - i);
    const dayStr = day.toISOString().split("T")[0];
    const dayLabel = day.toLocaleDateString("zh-CN", { weekday: "short" });
    const count = applications.filter((a) => {
      if (!a.applied_at) return false;
      return a.applied_at.startsWith(dayStr);
    }).length;
    dailyCounts.push({ label: dayLabel, count, dateStr: dayStr });
  }

  const maxCount = Math.max(...dailyCounts.map((d) => d.count), 1);
  const chartWidth = 280;
  const chartHeight = 100;
  const barWidth = 28;
  const gap = (chartWidth - barWidth * 7) / 8;
  const barMaxHeight = chartHeight - 20;

  let bars = "";
  dailyCounts.forEach((d, i) => {
    const barHeight = Math.max((d.count / maxCount) * barMaxHeight, 2);
    const x = gap + i * (barWidth + gap);
    const y = chartHeight - barHeight;
    bars += `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="3" fill="#0a66c2" opacity="0.85"/>`;
    bars += `<text x="${x + barWidth / 2}" y="${chartHeight + 12}" text-anchor="middle" font-size="9" fill="#666">${d.label}</text>`;
    if (d.count > 0) {
      bars += `<text x="${x + barWidth / 2}" y="${y - 3}" text-anchor="middle" font-size="9" fill="#333" font-weight="600">${d.count}</text>`;
    }
  });

  container.innerHTML = `<svg width="${chartWidth}" height="${chartHeight + 16}" viewBox="0 0 ${chartWidth} ${chartHeight + 16}" xmlns="http://www.w3.org/2000/svg">${bars}</svg>`;
}

function viewDetails(appId) {
  const app = allApplications.find((a) => a.id === appId);
  if (!app) return;

  // Toggle existing detail row
  const existing = document.getElementById(`detail-${appId}`);
  if (existing) {
    existing.remove();
    return;
  }

  const statusMap = { applied: "已投递", failed: "失败", pending: "待处理", pending_retry: "待重试", dry_run: "模拟" };
  const statusText = statusMap[app.status] || escapeHtml(app.status);

  // Build detail row
  const detailRow = document.createElement("tr");
  detailRow.id = `detail-${appId}`;
  detailRow.innerHTML = `
    <td colspan="7" style="padding:16px 20px;background:#f0f7ff;">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;font-size:13px;">
        <div><strong>职位名称：</strong> ${escapeHtml(app.job?.title || "-")}</div>
        <div><strong>公司：</strong> ${escapeHtml(app.job?.company || "-")}</div>
        <div><strong>地点：</strong> ${escapeHtml(app.job?.location || "-")}</div>
        <div><strong>匹配度：</strong> ${escapeHtml(String(app.job?.match_score ?? 0))}%</div>
        <div><strong>状态：</strong> <span class="badge ${escapeHtml(app.status)}">${statusText}</span></div>
        <div><strong>投递时间：</strong> ${app.applied_at ? escapeHtml(new Date(app.applied_at).toLocaleString("zh-CN")) : "-"}</div>
        <div><strong>投递方式：</strong> ${escapeHtml(app.apply_method || "-")}</div>
        <div><strong>错误信息：</strong> ${escapeHtml(app.error_message || "无")}</div>
      </div>
      ${app.job?.job_url ? `<div style="margin-top:8px;"><a href="${escapeHtml(app.job.job_url)}" target="_blank" style="color:#0a66c2;font-size:13px;">在 LinkedIn 上查看</a></div>` : ""}
    </td>
  `;

  // Insert after the current row
  const btn = document.querySelector(`[data-action="viewDetails"][data-id="${appId}"]`);
  if (btn) {
    btn.closest("tr").after(detailRow);
  }
}

function exportToCSV() {
  if (allApplications.length === 0) {
    alert("暂无投递记录可导出");
    return;
  }

  const headers = [
    "职位名称",
    "公司",
    "地点",
    "投递日期",
    "状态",
  ];
  const rows = allApplications.map((app) => [
    app.job?.title || "",
    app.job?.company || "",
    app.job?.location || "",
    app.applied_at ? new Date(app.applied_at).toLocaleDateString("zh-CN") : "",
    app.status || "",
  ]);

  let csv = "\uFEFF" + headers.join(",") + "\n"; // BOM for Excel Chinese support
  rows.forEach((row) => {
    csv += row.map((cell) => `"${cell}"`).join(",") + "\n";
  });

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `投递记录-${new Date().toISOString().split("T")[0]}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// Event listeners
positionFilter.addEventListener("input", filterAndRender);
companyFilter.addEventListener("input", filterAndRender);
statusFilter.addEventListener("change", filterAndRender);
refreshBtn.addEventListener("click", () => loadApplications(1));
exportBtn.addEventListener("click", exportToCSV);

// Event delegation for dynamic buttons (module scope can't use inline onclick)
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  const id = parseInt(btn.dataset.id);
  if (action === "viewDetails") viewDetails(id);
});

// Initialize
loadApplications(1);

// --- Connections Tab ---
const connCompanyFilter = document.getElementById("connCompanyFilter");
const connStatusFilter = document.getElementById("connStatusFilter");
const connTableBody = document.getElementById("connTableBody");

async function loadConnections() {
  try {
    const data = await apiCall("GET", "/connections?per_page=100");
    allConnections = data;
    filterAndRenderConnections();
    loadConnectionStats();
  } catch (error) {
    connTableBody.innerHTML =
      '<tr><td colspan="7" class="no-data">加载连接记录失败</td></tr>';
  }
}

function filterAndRenderConnections() {
  const companyText = connCompanyFilter.value.toLowerCase();
  const statusText = connStatusFilter.value;

  const filtered = allConnections.filter((conn) => {
    const matchCompany = !companyText || (conn.company || "").toLowerCase().includes(companyText);
    const matchStatus = !statusText || conn.status === statusText;
    return matchCompany && matchStatus;
  });

  connTableBody.innerHTML = "";
  if (filtered.length === 0) {
    connTableBody.innerHTML =
      '<tr><td colspan="7" class="no-data">暂无连接记录</td></tr>';
    return;
  }

  const typeLabels = {
    recruiter: "Recruiter",
    hiring_manager: "Hiring Manager",
    engineer: "Engineer",
  };
  const statusLabels = {
    sent: "已发送",
    accepted: "已接受",
    failed: "失败",
    pending: "待处理",
  };

  filtered.forEach((conn) => {
    const row = document.createElement("tr");
    const statusBadge = `<span class="badge ${escapeHtml(conn.status)}">${statusLabels[conn.status] || escapeHtml(conn.status)}</span>`;
    const sentDate = conn.sent_at
      ? new Date(conn.sent_at).toLocaleDateString("zh-CN")
      : "-";

    row.innerHTML = `
      <td><a href="${escapeHtml(conn.profile_url || "#")}" target="_blank" style="color:#0a66c2;text-decoration:none;">${escapeHtml(conn.person_name || "未知")}</a></td>
      <td>${escapeHtml(conn.title || "-")}</td>
      <td>${escapeHtml(conn.company || "-")}</td>
      <td>${escapeHtml(typeLabels[conn.person_type] || conn.person_type || "-")}</td>
      <td>${statusBadge}</td>
      <td>${sentDate}</td>
      <td>
        <button class="action-btn" data-action="viewConnDetails" data-id="${conn.id}">详情</button>
      </td>
    `;
    connTableBody.appendChild(row);
  });
}

async function loadConnectionStats() {
  try {
    const data = await apiCall("GET", "/connections/stats");
    document.getElementById("connectionStats").innerHTML = `
      <div class="stat-card">
        <div class="stat-label">总连接数</div>
        <div class="stat-value">${escapeHtml(String(data.total || 0))}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已发送</div>
        <div class="stat-value">${escapeHtml(String(data.sent || 0))}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已接受</div>
        <div class="stat-value">${escapeHtml(String(data.accepted || 0))}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">失败</div>
        <div class="stat-value">${escapeHtml(String(data.failed || 0))}</div>
      </div>
    `;
  } catch (error) {
    console.error("Error loading connection stats:", error);
  }
}

function viewConnDetails(connId) {
  const conn = allConnections.find((c) => c.id === connId);
  if (!conn) return;

  const existing = document.getElementById(`conn-detail-${connId}`);
  if (existing) {
    existing.remove();
    return;
  }

  const statusLabels = { sent: "已发送", accepted: "已接受", failed: "失败", pending: "待处理" };

  const detailRow = document.createElement("tr");
  detailRow.id = `conn-detail-${connId}`;
  detailRow.innerHTML = `
    <td colspan="7" style="padding:16px 20px;background:#f0f7ff;">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;font-size:13px;">
        <div><strong>姓名：</strong> ${escapeHtml(conn.person_name || "-")}</div>
        <div><strong>职称：</strong> ${escapeHtml(conn.title || "-")}</div>
        <div><strong>公司：</strong> ${escapeHtml(conn.company || "-")}</div>
        <div><strong>类型：</strong> ${escapeHtml(conn.person_type || "-")}</div>
        <div><strong>状态：</strong> <span class="badge ${escapeHtml(conn.status)}">${statusLabels[conn.status] || escapeHtml(conn.status)}</span></div>
        <div><strong>发送时间：</strong> ${conn.sent_at ? escapeHtml(new Date(conn.sent_at).toLocaleString("zh-CN")) : "-"}</div>
        <div style="grid-column:1/3;"><strong>消息：</strong> ${escapeHtml(conn.message || "无")}</div>
        <div style="grid-column:1/3;"><strong>错误：</strong> ${escapeHtml(conn.error_message || "无")}</div>
      </div>
      ${conn.profile_url ? `<div style="margin-top:8px;"><a href="${escapeHtml(conn.profile_url)}" target="_blank" style="color:#0a66c2;font-size:13px;">查看 LinkedIn 主页</a></div>` : ""}
    </td>
  `;

  const btn = document.querySelector(`[data-action="viewConnDetails"][data-id="${connId}"]`);
  if (btn) {
    btn.closest("tr").after(detailRow);
  }
}

// Connection filter listeners
connCompanyFilter.addEventListener("input", filterAndRenderConnections);
connStatusFilter.addEventListener("change", filterAndRenderConnections);

// Extend event delegation to handle connection actions
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  if (btn.dataset.action === "viewConnDetails") {
    viewConnDetails(parseInt(btn.dataset.id));
  }
});

// Auto-refresh every 30 seconds
setInterval(() => loadApplications(currentPage), 30000);
