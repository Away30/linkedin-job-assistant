/**
 * Service Worker - Central message bus and API proxy
 */

const BACKEND_URL = "http://localhost:8899/api/v1";
const BASE_URL = "http://localhost:8899";
let automationState = {
  is_running: false,
  jobs_applied: 0,
  jobs_failed: 0,
  jobs_found: 0,
};
let previousState = {
  is_running: false,
  captchaDetected: false,
  dailyLimitReached: false,
};

// Unified API fetch helper — attaches API Key from storage
async function apiFetch(path, options = {}) {
  const { apiKey } = await chrome.storage.local.get("apiKey");
  const headers = { ...(options.headers || {}), "Content-Type": "application/json" };
  if (apiKey) headers["X-API-Key"] = apiKey;
  return fetch(path.startsWith("http") ? path : `${BASE_URL}${path}`, { ...options, headers });
}

// Notification helper
function sendNotification(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: chrome.runtime.getURL("src/assets/icons/icon128.png"),
    title: title,
    message: message,
    priority: 2,
  });
}

// Check backend connectivity on startup
chrome.runtime.onInstalled.addListener(async () => {
  await checkBackendHealth();
  chrome.alarms.create("checkBackendHealth", { periodInMinutes: 1 });
});

// Alarm handler for health checks and status polling
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === "checkBackendHealth") {
    await checkBackendHealth();
  } else if (alarm.name === "pollAutomationStatus") {
    await pollAutomationStatus();
  }
});

// Main message listener
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  handleMessage(request, sender, sendResponse);
  return true; // Keep channel open for async response
});

async function handleMessage(request, sender, sendResponse) {
  const { action, payload } = request;

  try {
    switch (action) {
      case "checkHealth": {
        const healthResp = await fetch(`${BASE_URL}/health`);
        if (!healthResp.ok) {
          sendResponse({ success: false, error: `HTTP ${healthResp.status}` });
          break;
        }
        const health = await healthResp.json();
        sendResponse({ success: true, data: health });
        break;
      }

      case "startAutomation": {
        const startResp = await apiFetch(`${BACKEND_URL}/automation/start`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (!startResp.ok) {
          const errData = await startResp.json().catch(() => ({}));
          sendResponse({ success: false, error: errData.detail || `HTTP ${startResp.status}` });
          break;
        }
        const startRes = await startResp.json();
        automationState.is_running = true;
        await chrome.storage.local.set({ automationState });

        // Notification: automation started
        previousState.is_running = true;
        previousState.captchaDetected = false;
        previousState.dailyLimitReached = false;
        sendNotification("LinkedIn 智能投递", "自动投递已开始");

        sendResponse({ success: true, data: startRes });
        // Start polling status via chrome.alarms
        startStatusPolling();
        break;
      }

      case "stopAutomation": {
        const stopResp = await apiFetch(`${BACKEND_URL}/automation/stop`, {
          method: "POST",
        });
        if (!stopResp.ok) {
          sendResponse({ success: false, error: `HTTP ${stopResp.status}` });
          break;
        }
        const stopRes = await stopResp.json();
        automationState.is_running = false;
        await chrome.storage.local.set({ automationState });

        // Notification: automation stopped with summary
        const summary = `已投递: ${automationState.jobs_applied}, 失败: ${automationState.jobs_failed}, 发现: ${automationState.jobs_found}`;
        sendNotification("LinkedIn 智能投递 - 已停止", summary);
        previousState.is_running = false;

        sendResponse({ success: true, data: stopRes });
        break;
      }

      case "getStatus": {
        const statusResp = await apiFetch(`${BACKEND_URL}/automation/status`);
        if (!statusResp.ok) {
          sendResponse({ success: false, error: `HTTP ${statusResp.status}` });
          break;
        }
        const statusRes = await statusResp.json();
        sendResponse({ success: true, data: statusRes });
        break;
      }

      case "apiCall": {
        // Generic API proxy
        const apiResp = await apiFetch(`${BACKEND_URL}${payload.endpoint}`, {
          method: payload.method || "GET",
          headers: { "Content-Type": "application/json" },
          body: payload.body ? JSON.stringify(payload.body) : undefined,
        });
        if (!apiResp.ok) {
          const errData = await apiResp.json().catch(() => ({}));
          sendResponse({ success: false, error: errData.detail || `HTTP ${apiResp.status}` });
          break;
        }
        const apiRes = await apiResp.json();
        sendResponse({ success: true, data: apiRes });
        break;
      }

      case "getConnections": {
        const connResp = await apiFetch(`${BACKEND_URL}/connections${payload?.query || ""}`);
        if (!connResp.ok) {
          sendResponse({ success: false, error: `HTTP ${connResp.status}` });
          break;
        }
        const connData = await connResp.json();
        sendResponse({ success: true, data: connData });
        break;
      }

      case "getConnectionStats": {
        const statsResp = await apiFetch(`${BACKEND_URL}/connections/stats`);
        if (!statsResp.ok) {
          sendResponse({ success: false, error: `HTTP ${statsResp.status}` });
          break;
        }
        const statsData = await statsResp.json();
        sendResponse({ success: true, data: statsData });
        break;
      }

      default:
        sendResponse({ success: false, error: "Unknown action" });
    }
  } catch (error) {
    console.error("Message handler error:", error);
    sendResponse({ success: false, error: error.message });
  }
}

async function checkBackendHealth() {
  try {
    const response = await fetch(`${BASE_URL}/health`, {
      method: "GET",
    });
    const isHealthy = response.ok;
    await chrome.storage.local.set({
      backendConnected: isHealthy,
      lastHealthCheck: new Date().toISOString(),
    });
  } catch (error) {
    await chrome.storage.local.set({
      backendConnected: false,
      lastHealthCheck: new Date().toISOString(),
    });
  }
}

function startStatusPolling() {
  chrome.alarms.create("pollAutomationStatus", { periodInMinutes: 0.1 }); // ~6s
}

function stopStatusPolling() {
  chrome.alarms.clear("pollAutomationStatus");
}

async function pollAutomationStatus() {
  if (!automationState.is_running) {
    stopStatusPolling();
    return;
  }

  try {
    const response = await apiFetch(`${BACKEND_URL}/automation/status`);
    const status = await response.json();

    automationState = {
      is_running: status.is_running,
      jobs_applied: status.jobs_applied || 0,
      jobs_failed: status.jobs_failed || 0,
      jobs_found: status.jobs_found || 0,
      jobs_dry_run: status.jobs_dry_run || 0,
      connections_sent: status.connections_sent || 0,
      status_message: status.status_message || "",
      daily_applies_remaining: status.daily_applies_remaining,
      current_job: status.current_job || null,
    };

    await chrome.storage.local.set({ automationState });

    // Check for state transitions and send notifications

    // Login required detection
    const isLoginRequired = status.status_message && status.status_message.includes("手动登录");
    if (isLoginRequired && !previousState.loginNotified) {
      sendNotification("LinkedIn 智能投递 - 需要登录", "请在打开的浏览器窗口中登录 LinkedIn，你有 5 分钟时间。");
      previousState.loginNotified = true;
    }

    // CAPTCHA detection
    const isCaptcha = status.status_message && status.status_message.toLowerCase().includes("验证码");
    if (isCaptcha && !previousState.captchaDetected) {
      sendNotification("LinkedIn 智能投递 - 验证码", "检测到验证码，请在浏览器窗口中手动完成");
      previousState.captchaDetected = true;
    }
    if (!isCaptcha && previousState.captchaDetected) {
      previousState.captchaDetected = false;
    }
    if (!isLoginRequired) {
      previousState.loginNotified = false;
    }

    // Daily limit reached
    const isDailyLimit = status.status_message && (
      status.status_message.includes("每日投递上限") ||
      status.status_message.toLowerCase().includes("daily limit") ||
      status.status_message.toLowerCase().includes("rate limit")
    );
    if (isDailyLimit && !previousState.dailyLimitReached) {
      sendNotification("LinkedIn 智能投递 - 每日上限", "已达到每日投递上限，自动投递已停止");
      previousState.dailyLimitReached = true;
    }

    // Automation completed (was running, now stopped)
    if (previousState.is_running && !status.is_running) {
      const summary = `投递完成。已投递: ${status.jobs_applied}, 失败: ${status.jobs_failed}`;
      sendNotification("LinkedIn 智能投递 - 已完成", summary);
      previousState.is_running = false;
    }

    // Broadcast to all popup/options windows
    chrome.runtime.sendMessage({
      action: "statusUpdate",
      payload: automationState,
    }).catch(() => {
      // Ignore if no receivers (popup closed)
    });

    // Stop polling if automation finished
    if (!automationState.is_running) {
      stopStatusPolling();
    }
  } catch (error) {
    console.error("Status polling error:", error);
  }
}
