/**
 * Options Page - Manage filters, resumes, and settings
 */

import { escapeHtml } from "../utils/sanitize.js";

const API_BASE = "http://localhost:8899/api/v1";

// DOM elements
const filterName = document.getElementById("filterName");
const filterKeywords = document.getElementById("filterKeywords");
const filterLocation = document.getElementById("filterLocation");
const filterJobType = document.getElementById("filterJobType");
const filterExperience = document.getElementById("filterExperience");
const easyApplyOnly = document.getElementById("easyApplyOnly");
const saveFilterBtn = document.getElementById("saveFilterBtn");
const filterList = document.getElementById("filterList");

const resumeName = document.getElementById("resumeName");
const resumeFile = document.getElementById("resumeFile");
const resumeRoles = document.getElementById("resumeRoles");
const resumeDefault = document.getElementById("resumeDefault");
const uploadResumeBtn = document.getElementById("uploadResumeBtn");
const resumeList = document.getElementById("resumeList");

const maxAppliesPerDay = document.getElementById("maxAppliesPerDay");
const maxConnectsPerDay = document.getElementById("maxConnectsPerDay");
const minDelay = document.getElementById("minDelay");
const maxDelay = document.getElementById("maxDelay");
const warmupEnabled = document.getElementById("warmupEnabled");
const saveSafetyBtn = document.getElementById("saveSafetyBtn");

const messageDiv = document.getElementById("message");
const testConnectionBtn = document.getElementById("testConnectionBtn");
const testConnectionResult = document.getElementById("testConnectionResult");
const apiKeyInput = document.getElementById("apiKeyInput");
const saveApiKeyBtn = document.getElementById("saveApiKeyBtn");

// Helper to show messages
function showMessage(text, type = "success") {
  messageDiv.textContent = text;
  messageDiv.className = `message ${type}`;
  messageDiv.style.display = "block";
  setTimeout(() => {
    messageDiv.style.display = "none";
  }, 3000);
}

// Helper for API calls from options page
async function apiCall(method, path, body = null) {
  try {
    const options = {
      method,
      headers: { "Content-Type": "application/json" },
    };
    if (body) options.body = JSON.stringify(body);
    const response = await fetch(`${API_BASE}${path}`, options);
    return await response.json();
  } catch (error) {
    console.error("API call failed:", error);
    throw error;
  }
}

// Load and display filters
async function loadFilters() {
  try {
    const filters = await apiCall("GET", "/filters");
    filterList.innerHTML = "";
    filters.forEach((f) => {
      const item = document.createElement("div");
      item.className = "filter-item";
      item.innerHTML = `
        <div>
          <div class="filter-item-name">${escapeHtml(f.name)}</div>
          <div class="filter-item-details">${escapeHtml(f.keywords)} • ${escapeHtml(f.location)}</div>
        </div>
        <button class="btn-danger" onclick="deleteFilter(${f.id})">Delete</button>
      `;
      filterList.appendChild(item);
    });
  } catch (error) {
    console.error("Error loading filters:", error);
  }
}

async function deleteFilter(id) {
  try {
    await apiCall("DELETE", `/filters/${id}`);
    loadFilters();
    showMessage("Filter deleted");
  } catch (error) {
    showMessage("Error deleting filter", "error");
  }
}

// Load and display resumes
async function loadResumes() {
  try {
    const resumes = await apiCall("GET", "/resumes");
    resumeList.innerHTML = "";
    resumes.forEach((r) => {
      const item = document.createElement("div");
      item.className = "resume-item";
      const badge = r.is_default ? '<span class="resume-item-badge">DEFAULT</span>' : "";
      item.innerHTML = `
        <div>
          <div class="resume-item-name">${escapeHtml(r.name)}</div>
          <div class="resume-item-details">${escapeHtml(r.target_roles || "No specific roles")}</div>
        </div>
        <div>
          ${badge}
          <button class="btn-danger" onclick="deleteResume(${r.id})">Delete</button>
        </div>
      `;
      resumeList.appendChild(item);
    });
  } catch (error) {
    console.error("Error loading resumes:", error);
  }
}

async function deleteResume(id) {
  try {
    await apiCall("DELETE", `/resumes/${id}`);
    loadResumes();
    showMessage("Resume deleted");
  } catch (error) {
    showMessage("Error deleting resume", "error");
  }
}

// Save filter
saveFilterBtn.addEventListener("click", async () => {
  try {
    await apiCall("POST", "/filters", {
      name: filterName.value,
      keywords: filterKeywords.value,
      location: filterLocation.value,
      job_type: filterJobType.value.trim(),
      experience_level: filterExperience.value || null,
      easy_apply_only: easyApplyOnly.checked,
    });
    filterName.value = "";
    filterKeywords.value = "";
    filterLocation.value = "";
    filterJobType.value = "";
    filterExperience.value = "";
    easyApplyOnly.checked = false;
    loadFilters();
    showMessage("Filter saved successfully");
  } catch (error) {
    showMessage("Error saving filter", "error");
  }
});

// Upload resume
uploadResumeBtn.addEventListener("click", async () => {
  if (!resumeName.value || !resumeFile.files.length) {
    showMessage("Please enter name and select file", "error");
    return;
  }
  try {
    const formData = new FormData();
    formData.append("file", resumeFile.files[0]);
    formData.append("name", resumeName.value);
    formData.append("target_roles", resumeRoles.value);
    formData.append("is_default", resumeDefault.checked);

    const response = await fetch(`${API_BASE}/resumes`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error("Upload failed");

    resumeName.value = "";
    resumeFile.value = "";
    resumeRoles.value = "";
    resumeDefault.checked = false;
    loadResumes();
    showMessage("Resume uploaded successfully");
  } catch (error) {
    showMessage("Error uploading resume", "error");
  }
});

// Save safety settings (sync to backend)
saveSafetyBtn.addEventListener("click", async () => {
  try {
    const safetyPayload = {
      max_applies_per_day: parseInt(maxAppliesPerDay.value),
      max_connects_per_day: parseInt(maxConnectsPerDay.value),
      action_delay_min: parseInt(minDelay.value),
      action_delay_max: parseInt(maxDelay.value),
    };

    // Save to backend
    const resp = await fetch(`${API_BASE}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(safetyPayload),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showMessage(err.detail || "Failed to sync settings to backend", "error");
      return;
    }

    // Also save locally for backup
    await chrome.storage.local.set({
      safetySettings: safetyPayload,
    });
    showMessage("Safety settings synced to backend");
  } catch (error) {
    showMessage("Error saving settings", "error");
  }
});

// Test Connection
testConnectionBtn.addEventListener("click", async () => {
  testConnectionResult.textContent = "Testing...";
  testConnectionResult.style.color = "#666";
  try {
    const response = await fetch("http://localhost:8899/health");
    if (response.ok) {
      const data = await response.json();
      testConnectionResult.textContent = `Connected! Status: ${data.status || "ok"}`;
      testConnectionResult.style.color = "#155724";
    } else {
      testConnectionResult.textContent = `Backend returned HTTP ${response.status}`;
      testConnectionResult.style.color = "#721c24";
    }
  } catch (error) {
    testConnectionResult.textContent = "Connection failed: " + error.message;
    testConnectionResult.style.color = "#721c24";
  }
});

// API Key save/load
saveApiKeyBtn.addEventListener("click", async () => {
  const key = apiKeyInput.value.trim();
  if (!key) {
    showMessage("Please enter an API key", "error");
    return;
  }
  await chrome.storage.local.set({ apiKey: key });
  showMessage("API key saved");
});

async function loadApiKey() {
  const data = await chrome.storage.local.get("apiKey");
  if (data.apiKey) {
    apiKeyInput.value = data.apiKey;
  }
}

// Initialize
loadFilters();
loadResumes();
loadSettings();
loadApiKey();

async function loadSettings() {
  try {
    const data = await apiCall("GET", "/settings");
    maxAppliesPerDay.value = data.max_applies_per_day || 25;
    maxConnectsPerDay.value = data.max_connects_per_day || 20;
    minDelay.value = data.action_delay_min || 3;
    maxDelay.value = data.action_delay_max || 12;
  } catch (error) {
    console.error("Error loading settings:", error);
  }
}
