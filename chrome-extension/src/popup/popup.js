/**
 * Popup Script
 */

// DOM elements
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const filterSelect = document.getElementById("filterSelect");
const healthIndicator = document.getElementById("healthIndicator");
const statusEl = document.getElementById("status");
const appliedEl = document.getElementById("applied");
const failedEl = document.getElementById("failed");
const dryRunRowEl = document.getElementById("dryRunRow");
const dryRunCountEl = document.getElementById("dryRunCount");
const dashboardBtn = document.getElementById("dashboardBtn");
const settingsBtn = document.getElementById("settingsBtn");
const backendStatusEl = document.getElementById("backendStatus");
const progressRow = document.getElementById("progressRow");
const progressEl = document.getElementById("progress");
const currentJobRow = document.getElementById("currentJobRow");
const currentJobEl = document.getElementById("currentJob");
const statusMessageEl = document.getElementById("statusMessage");
const setupBanner = document.getElementById("setupBanner");
const bannerMessage = document.getElementById("bannerMessage");
const bannerSettingsBtn = document.getElementById("bannerSettingsBtn");

function applyDryRunCount(count) {
  const value = Number(count) || 0;
  if (!dryRunRowEl || !dryRunCountEl) return;
  dryRunCountEl.textContent = value;
  dryRunRowEl.style.display = value > 0 ? "flex" : "none";
}

// Initialize popup — script is at bottom of body, DOM already ready
checkFirstRun();
checkBackendHealth();
loadFilters();
attachEventListeners();
updateStatus();

// First-run detection: check if API key is configured
async function checkFirstRun() {
  const { apiKey } = await chrome.storage.local.get("apiKey");
  if (!apiKey) {
    setupBanner.style.display = "block";
    bannerMessage.textContent = "请先在设置页配置 API Key。启动后端时终端会显示 Key。";
  }
}

function showStatusMessage(text, type) {
  statusMessageEl.textContent = text;
  if (type === "error") {
    statusMessageEl.style.background = "#f8d7da";
    statusMessageEl.style.color = "#721c24";
    statusMessageEl.style.border = "1px solid #f5c6cb";
  } else {
    statusMessageEl.style.background = "#d4edda";
    statusMessageEl.style.color = "#155724";
    statusMessageEl.style.border = "1px solid #c3e6cb";
  }
  statusMessageEl.style.display = "block";
  setTimeout(() => {
    statusMessageEl.style.display = "none";
  }, 4000);
}

async function checkBackendHealth() {
  chrome.runtime.sendMessage({ action: "checkHealth" }, (response) => {
    if (response?.success) {
      healthIndicator.innerHTML =
        '<span class="dot green"></span><span class="text">后端已连接</span>';
      backendStatusEl.textContent = "在线";
      // Don't enable start if no API key
      chrome.storage.local.get("apiKey", ({ apiKey }) => {
        startBtn.disabled = !apiKey;
      });
    } else {
      healthIndicator.innerHTML =
        '<span class="dot red"></span><span class="text">后端离线</span>';
      backendStatusEl.textContent = "离线";
      startBtn.disabled = true;
    }
  });
}

async function loadFilters() {
  chrome.runtime.sendMessage(
    { action: "apiCall", payload: { endpoint: "/filters" } },
    (response) => {
      if (response?.success && response.data) {
        const filters = response.data;
        filters.forEach((filter) => {
          const option = document.createElement("option");
          option.value = filter.id;
          option.textContent = filter.name;
          filterSelect.appendChild(option);
        });
        // API key works — hide setup banner
        setupBanner.style.display = "none";
      } else if (response?.error && response.error.includes("API")) {
        // API key issue — show banner if not already
        setupBanner.style.display = "block";
        bannerMessage.textContent = "API Key 未配置或无效，请前往设置页填写正确的 Key。";
      }
    }
  );
}

async function updateStatus() {
  chrome.runtime.sendMessage({ action: "getStatus" }, (response) => {
    if (response?.success) {
      const status = response.data;
      statusEl.textContent = status.status_message || (status.is_running ? "运行中..." : "空闲");
      appliedEl.textContent = status.jobs_applied || 0;
      failedEl.textContent = status.jobs_failed || 0;
      applyDryRunCount(status.jobs_dry_run);

      // Progress display
      const applied = status.jobs_applied || 0;
      const remaining = status.daily_applies_remaining || 0;
      const dailyTotal = applied + remaining;
      if (dailyTotal > 0) {
        progressRow.style.display = "flex";
        progressEl.textContent = `${applied} / ${dailyTotal} 今日`;
      } else {
        progressRow.style.display = "none";
      }

      // Current job display
      if (status.current_job) {
        currentJobRow.style.display = "flex";
        currentJobEl.textContent = status.current_job;
      } else {
        currentJobRow.style.display = "none";
      }

      startBtn.disabled = status.is_running;
      stopBtn.disabled = !status.is_running;
    } else if (!response?.success && response?.error?.includes("API")) {
      statusEl.textContent = "API Key 未配置";
    }
  });
}

function attachEventListeners() {
  startBtn.addEventListener("click", handleStart);
  stopBtn.addEventListener("click", handleStop);
  dashboardBtn.addEventListener("click", () => {
    chrome.tabs.create({
      url: chrome.runtime.getURL("src/dashboard/dashboard.html"),
    });
  });
  settingsBtn.addEventListener("click", () => {
    chrome.runtime.openOptionsPage();
  });
  bannerSettingsBtn.addEventListener("click", () => {
    chrome.runtime.openOptionsPage();
  });

  // Listen for status updates from service worker
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "statusUpdate") {
      appliedEl.textContent = request.payload.jobs_applied ?? 0;
      failedEl.textContent = request.payload.jobs_failed ?? 0;
      applyDryRunCount(request.payload.jobs_dry_run);
      statusEl.textContent = request.payload.status_message || (request.payload.is_running ? "运行中..." : "空闲");
      startBtn.disabled = request.payload.is_running;
      stopBtn.disabled = !request.payload.is_running;

      // Update progress
      const applied = request.payload.jobs_applied || 0;
      const remaining = request.payload.daily_applies_remaining || 0;
      const dailyTotal = applied + remaining;
      if (dailyTotal > 0) {
        progressRow.style.display = "flex";
        progressEl.textContent = `${applied} / ${dailyTotal} 今日`;
      }

      // Update current job
      if (request.payload.current_job) {
        currentJobRow.style.display = "flex";
        currentJobEl.textContent = request.payload.current_job;
      } else {
        currentJobRow.style.display = "none";
      }
    }
  });
}

async function handleStart() {
  const filterId = filterSelect.value;
  if (!filterId) {
    showStatusMessage("请先选择搜索条件", "error");
    return;
  }

  const dryRun = document.getElementById("dryRunToggle")?.checked || false;
  const enableNetworking = document.getElementById("networkingToggle")?.checked || false;

  chrome.runtime.sendMessage(
    {
      action: "startAutomation",
      payload: { filter_id: filterId, max_applies: 10, dry_run: dryRun, enable_networking: enableNetworking },
    },
    (response) => {
      if (response?.success) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusEl.textContent = "启动中...";
        showStatusMessage("自动化已启动", "success");
      } else {
        showStatusMessage("启动失败：" + (response?.error || "未知错误"), "error");
      }
    }
  );
}

async function handleStop() {
  chrome.runtime.sendMessage({ action: "stopAutomation" }, (response) => {
    if (response?.success) {
      startBtn.disabled = false;
      stopBtn.disabled = true;
      statusEl.textContent = "正在停止...";
      showStatusMessage("自动化已停止", "success");
    }
  });
}

// Check health every 10 seconds
setInterval(checkBackendHealth, 10000);

// Update status every 2 seconds when running
setInterval(updateStatus, 2000);
