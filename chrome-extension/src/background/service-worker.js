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
        const startResp = await fetch(`${BACKEND_URL}/automation/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
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
        sendNotification("Smart Apply", "Automation started");

        sendResponse({ success: true, data: startRes });
        // Start polling status via chrome.alarms
        startStatusPolling();
        break;
      }

      case "stopAutomation": {
        const stopResp = await fetch(`${BACKEND_URL}/automation/stop`, {
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
        const summary = `Applied: ${automationState.jobs_applied}, Failed: ${automationState.jobs_failed}, Found: ${automationState.jobs_found}`;
        sendNotification("Smart Apply - Stopped", summary);
        previousState.is_running = false;

        sendResponse({ success: true, data: stopRes });
        break;
      }

      case "getStatus": {
        const statusResp = await fetch(`${BACKEND_URL}/automation/status`);
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
        const apiResp = await fetch(`${BACKEND_URL}${payload.endpoint}`, {
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
    const response = await fetch(`${BACKEND_URL}/automation/status`);
    const status = await response.json();

    automationState = {
      is_running: status.is_running,
      jobs_applied: status.jobs_applied || 0,
      jobs_failed: status.jobs_failed || 0,
      jobs_found: status.jobs_found || 0,
      status_message: status.status_message || "",
      daily_applies_remaining: status.daily_applies_remaining,
      current_job: status.current_job || null,
    };

    await chrome.storage.local.set({ automationState });

    // Check for state transitions and send notifications

    // CAPTCHA detection
    const isCaptcha = status.status_message && status.status_message.toLowerCase().includes("captcha");
    if (isCaptcha && !previousState.captchaDetected) {
      sendNotification("Smart Apply - CAPTCHA", "CAPTCHA detected, please solve it in the browser window");
      previousState.captchaDetected = true;
    }
    if (!isCaptcha && previousState.captchaDetected) {
      previousState.captchaDetected = false;
    }

    // Daily limit reached
    const isDailyLimit = status.status_message && (
      status.status_message.toLowerCase().includes("daily limit") ||
      status.status_message.toLowerCase().includes("rate limit")
    );
    if (isDailyLimit && !previousState.dailyLimitReached) {
      sendNotification("Smart Apply - Daily Limit", "Daily limit reached, automation stopped");
      previousState.dailyLimitReached = true;
    }

    // Automation completed (was running, now stopped)
    if (previousState.is_running && !status.is_running) {
      const summary = `Completed. Applied: ${status.jobs_applied}, Failed: ${status.jobs_failed}`;
      sendNotification("Smart Apply - Completed", summary);
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
