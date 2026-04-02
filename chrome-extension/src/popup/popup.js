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
const dashboardBtn = document.getElementById("dashboardBtn");
const settingsBtn = document.getElementById("settingsBtn");
const backendStatusEl = document.getElementById("backendStatus");
const progressRow = document.getElementById("progressRow");
const progressEl = document.getElementById("progress");
const currentJobRow = document.getElementById("currentJobRow");
const currentJobEl = document.getElementById("currentJob");
const statusMessageEl = document.getElementById("statusMessage");

// Initialize popup
document.addEventListener("DOMContentLoaded", async () => {
  await checkBackendHealth();
  await loadFilters();
  attachEventListeners();
  await updateStatus();
});

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
        '<span class="dot green"></span><span class="text">Backend connected</span>';
      backendStatusEl.textContent = "online";
      startBtn.disabled = false;
    } else {
      healthIndicator.innerHTML =
        '<span class="dot red"></span><span class="text">Backend offline</span>';
      backendStatusEl.textContent = "offline";
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
      }
    }
  );
}

async function updateStatus() {
  chrome.runtime.sendMessage({ action: "getStatus" }, (response) => {
    if (response?.success) {
      const status = response.data;
      statusEl.textContent = status.status_message || (status.is_running ? "Running..." : "Idle");
      appliedEl.textContent = status.jobs_applied || 0;
      failedEl.textContent = status.jobs_failed || 0;

      // Progress display: "Applied X / Y today"
      const applied = status.jobs_applied || 0;
      const remaining = status.daily_applies_remaining || 0;
      const dailyTotal = applied + remaining;
      if (dailyTotal > 0) {
        progressRow.style.display = "flex";
        progressEl.textContent = `${applied} / ${dailyTotal} today`;
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
    } else {
      statusEl.textContent = "Error: backend unreachable";
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

  // Listen for status updates from service worker
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "statusUpdate") {
      appliedEl.textContent = request.payload.jobs_applied ?? 0;
      failedEl.textContent = request.payload.jobs_failed ?? 0;
      statusEl.textContent = request.payload.status_message || (request.payload.is_running ? "Running..." : "Idle");
      startBtn.disabled = request.payload.is_running;
      stopBtn.disabled = !request.payload.is_running;

      // Update progress
      const applied = request.payload.jobs_applied || 0;
      const remaining = request.payload.daily_applies_remaining || 0;
      const dailyTotal = applied + remaining;
      if (dailyTotal > 0) {
        progressRow.style.display = "flex";
        progressEl.textContent = `${applied} / ${dailyTotal} today`;
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
    showStatusMessage("Please select a search filter", "error");
    return;
  }

  const dryRun = document.getElementById("dryRunToggle")?.checked || false;

  chrome.runtime.sendMessage(
    {
      action: "startAutomation",
      payload: { filter_id: filterId, max_applies: 10, dry_run: dryRun },
    },
    (response) => {
      if (response?.success) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusEl.textContent = "Starting...";
        showStatusMessage("Automation started", "success");
      } else {
        showStatusMessage("Failed to start: " + (response?.error || "Unknown error"), "error");
      }
    }
  );
}

async function handleStop() {
  chrome.runtime.sendMessage({ action: "stopAutomation" }, (response) => {
    if (response?.success) {
      startBtn.disabled = false;
      stopBtn.disabled = true;
      statusEl.textContent = "Stopping...";
      showStatusMessage("Automation stopped", "success");
    }
  });
}

// Check health every 10 seconds
setInterval(checkBackendHealth, 10000);

// Update status every 2 seconds when running
setInterval(updateStatus, 2000);
