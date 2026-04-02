/**
 * Application Tracker Dashboard - Display and manage applications
 */

import { escapeHtml } from "../utils/sanitize.js";

const API_BASE = "http://localhost:8899/api/v1";
const positionFilter = document.getElementById("positionFilter");
const companyFilter = document.getElementById("companyFilter");
const statusFilter = document.getElementById("statusFilter");
const tableBody = document.getElementById("tableBody");
const exportBtn = document.getElementById("exportBtn");
const refreshBtn = document.getElementById("refreshBtn");

const PAGE_SIZE = 20;
let currentPage = 1;
let allApplications = [];

async function loadApplications(page) {
  if (page === undefined) {
    page = currentPage;
  }
  try {
    const response = await fetch(`${API_BASE}/applications?per_page=${PAGE_SIZE}&page=${page}`);
    const data = await response.json();
    allApplications = data;
    currentPage = page;
    filterAndRender();
    loadStats();
    updatePagination();
  } catch (error) {
    tableBody.innerHTML =
      '<tr><td colspan="6" class="no-data">Error loading applications</td></tr>';
  }
}

function updatePagination() {
  const container = document.getElementById("paginationContainer");
  if (!container) return;
  container.innerHTML = "";

  const prevBtn = document.createElement("button");
  prevBtn.textContent = "Previous";
  prevBtn.disabled = currentPage <= 1;
  prevBtn.addEventListener("click", () => loadApplications(currentPage - 1));

  const pageInfo = document.createElement("span");
  pageInfo.textContent = ` Page ${currentPage} `;
  pageInfo.style.margin = "0 12px";
  pageInfo.style.lineHeight = "36px";
  pageInfo.style.color = "#333";
  pageInfo.style.fontSize = "13px";

  const nextBtn = document.createElement("button");
  nextBtn.textContent = "Next";
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
      '<tr><td colspan="6" class="no-data">No applications found</td></tr>';
    return;
  }

  filtered.forEach((app) => {
    const row = document.createElement("tr");
    const statusBadge = `<span class="badge ${escapeHtml(app.status)}">${escapeHtml(app.status)}</span>`;
    const appliedDate = app.applied_at
      ? new Date(app.applied_at).toLocaleDateString()
      : "N/A";

    // Match score display
    const score = app.job?.match_score ?? 0;
    const scoreColor = score >= 70 ? "#0a66c2" : score >= 40 ? "#e8a838" : "#dc3545";
    const scoreBadge = `<span style="color:${scoreColor};font-weight:700;">${score}%</span>`;

    row.innerHTML = `
      <td>${escapeHtml(app.job?.title || "Unknown")}</td>
      <td>${escapeHtml(app.job?.company || "Unknown")}</td>
      <td>${escapeHtml(app.job?.location || "N/A")}</td>
      <td>${scoreBadge}</td>
      <td>${appliedDate}</td>
      <td>${statusBadge}</td>
      <td>
        <button class="action-btn" onclick="viewDetails(${app.id})">View</button>
      </td>
    `;
    tableBody.appendChild(row);
  });
}

async function loadStats() {
  try {
    // Use already-loaded allApplications instead of fetching again
    const data = allApplications;

    const applied = data.filter((a) => a.status === "applied").length;
    const failed = data.filter((a) => a.status === "failed").length;
    const pending = data.filter((a) => a.status === "pending").length;

    document.getElementById("stats").innerHTML = `
      <div class="stat-card">
        <div class="stat-label">Total Applied</div>
        <div class="stat-value">${escapeHtml(String(applied))}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Failed</div>
        <div class="stat-value">${escapeHtml(String(failed))}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Pending</div>
        <div class="stat-value">${escapeHtml(String(pending))}</div>
      </div>
      <div class="stat-card" id="chartCard">
        <div class="stat-label">Daily Applications (Last 7 Days)</div>
        <div id="dailyChart"></div>
      </div>
    `;
    renderDailyChart(data);
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
    const dayLabel = day.toLocaleDateString("en-US", { weekday: "short" });
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

  // Build detail row
  const detailRow = document.createElement("tr");
  detailRow.id = `detail-${appId}`;
  detailRow.innerHTML = `
    <td colspan="7" style="padding:16px 20px;background:#f0f7ff;">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;font-size:13px;">
        <div><strong>Job Title:</strong> ${escapeHtml(app.job?.title || "N/A")}</div>
        <div><strong>Company:</strong> ${escapeHtml(app.job?.company || "N/A")}</div>
        <div><strong>Location:</strong> ${escapeHtml(app.job?.location || "N/A")}</div>
        <div><strong>Match Score:</strong> ${escapeHtml(String(app.job?.match_score ?? 0))}%</div>
        <div><strong>Status:</strong> <span class="badge ${escapeHtml(app.status)}">${escapeHtml(app.status)}</span></div>
        <div><strong>Applied:</strong> ${app.applied_at ? escapeHtml(new Date(app.applied_at).toLocaleString()) : "N/A"}</div>
        <div><strong>Method:</strong> ${escapeHtml(app.apply_method || "N/A")}</div>
        <div><strong>Error:</strong> ${escapeHtml(app.error_message || "None")}</div>
      </div>
      ${app.job?.job_url ? `<div style="margin-top:8px;"><a href="${escapeHtml(app.job.job_url)}" target="_blank" style="color:#0a66c2;font-size:13px;">View on LinkedIn</a></div>` : ""}
    </td>
  `;

  // Insert after the current row
  const btn = document.querySelector(`[onclick="viewDetails(${appId})"]`);
  if (btn) {
    btn.closest("tr").after(detailRow);
  }
}

function exportToCSV() {
  if (allApplications.length === 0) {
    alert("No applications to export");
    return;
  }

  const headers = [
    "Job Title",
    "Company",
    "Location",
    "Applied Date",
    "Status",
  ];
  const rows = allApplications.map((app) => [
    app.job?.title || "",
    app.job?.company || "",
    app.job?.location || "",
    app.applied_at ? new Date(app.applied_at).toLocaleDateString() : "",
    app.status || "",
  ]);

  let csv = headers.join(",") + "\n";
  rows.forEach((row) => {
    csv += row.map((cell) => `"${cell}"`).join(",") + "\n";
  });

  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `applications-${new Date().toISOString().split("T")[0]}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// Event listeners
positionFilter.addEventListener("input", filterAndRender);
companyFilter.addEventListener("input", filterAndRender);
statusFilter.addEventListener("change", filterAndRender);
refreshBtn.addEventListener("click", () => loadApplications(1));
exportBtn.addEventListener("click", exportToCSV);

// Initialize
loadApplications(1);
