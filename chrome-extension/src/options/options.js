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
const filterDatePosted = document.getElementById("filterDatePosted");
const filterMinScore = document.getElementById("filterMinScore");
const filterRequiredSkills = document.getElementById("filterRequiredSkills");
const filterPreferredSkills = document.getElementById("filterPreferredSkills");
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

// Helper for API calls from options page — includes API Key
async function apiCall(method, path, body = null) {
  try {
    const { apiKey } = await chrome.storage.local.get("apiKey");
    const options = {
      method,
      headers: { "Content-Type": "application/json" },
    };
    if (apiKey) options.headers["X-API-Key"] = apiKey;
    if (body) options.body = JSON.stringify(body);
    const response = await fetch(`${API_BASE}${path}`, options);
    const data = await response.json();
    if (data.detail && response.status === 401) {
      throw new Error("API 密钥未配置，请先在上方填写 API 密钥。");
    }
    return data;
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
      const dateLabel = f.date_posted === "past-24h" ? "24h内" :
                        f.date_posted === "past-week" ? "一周内" :
                        f.date_posted === "past-month" ? "一月内" : "不限";
      const skillsLabel = f.required_skills ? ` • 技能: ${escapeHtml(f.required_skills)}` : "";
      item.innerHTML = `
        <div>
          <div class="filter-item-name">${escapeHtml(f.name)}</div>
          <div class="filter-item-details">${escapeHtml(f.keywords)} • ${escapeHtml(f.location)} • ${dateLabel}${skillsLabel}</div>
        </div>
        <button class="btn-danger" data-action="deleteFilter" data-id="${f.id}">删除</button>
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
    showMessage("筛选条件已删除");
  } catch (error) {
    showMessage("删除筛选条件失败", "error");
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
      const badge = r.is_default ? '<span class="resume-item-badge">默认</span>' : "";
      item.innerHTML = `
        <div>
          <div class="resume-item-name">${escapeHtml(r.name)}</div>
          <div class="resume-item-details">${escapeHtml(r.target_roles || "无指定职位")}</div>
        </div>
        <div>
          ${badge}
          <button class="btn-danger" data-action="deleteResume" data-id="${r.id}">删除</button>
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
    showMessage("简历已删除");
  } catch (error) {
    showMessage("删除简历失败", "error");
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
      date_posted: filterDatePosted.value || null,
      min_match_score: parseInt(filterMinScore.value) || 40,
      required_skills: filterRequiredSkills.value.trim() || null,
      preferred_skills: filterPreferredSkills.value.trim() || null,
    });
    filterName.value = "";
    filterKeywords.value = "";
    filterLocation.value = "";
    filterJobType.value = "";
    filterExperience.value = "";
    easyApplyOnly.checked = true;
    filterDatePosted.value = "past-24h";
    filterMinScore.value = "40";
    filterRequiredSkills.value = "";
    filterPreferredSkills.value = "";
    loadFilters();
    showMessage("筛选条件已保存");
  } catch (error) {
    showMessage("保存筛选条件失败", "error");
  }
});

// Upload resume
uploadResumeBtn.addEventListener("click", async () => {
  if (!resumeName.value || !resumeFile.files.length) {
    showMessage("请输入简历名称并选择文件", "error");
    return;
  }
  try {
    const formData = new FormData();
    formData.append("file", resumeFile.files[0]);
    formData.append("name", resumeName.value);
    formData.append("target_roles", resumeRoles.value);
    formData.append("is_default", resumeDefault.checked);

    const { apiKey } = await chrome.storage.local.get("apiKey");
    const headers = {};
    if (apiKey) headers["X-API-Key"] = apiKey;
    const response = await fetch(`${API_BASE}/resumes`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) throw new Error("上传失败");

    resumeName.value = "";
    resumeFile.value = "";
    resumeRoles.value = "";
    resumeDefault.checked = false;
    loadResumes();
    showMessage("简历上传成功");
  } catch (error) {
    showMessage("上传简历失败", "error");
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
      warmup_enabled: warmupEnabled.checked,
    };

    // Save to backend via apiCall (includes API Key)
    await apiCall("POST", "/settings", safetyPayload);

    // Also save locally for backup
    await chrome.storage.local.set({
      safetySettings: safetyPayload,
    });
    showMessage("安全设置已同步到后端");
  } catch (error) {
    showMessage("保存设置失败", "error");
  }
});

// Test Connection
testConnectionBtn.addEventListener("click", async () => {
  testConnectionResult.textContent = "测试中...";
  testConnectionResult.style.color = "#666";
  try {
    const response = await fetch("http://localhost:8899/health");
    if (response.ok) {
      const data = await response.json();
      testConnectionResult.textContent = `已连接！状态：${data.status || "正常"}`;
      testConnectionResult.style.color = "#155724";
    } else {
      testConnectionResult.textContent = `后端返回 HTTP ${response.status}`;
      testConnectionResult.style.color = "#721c24";
    }
  } catch (error) {
    testConnectionResult.textContent = "连接失败：" + error.message;
    testConnectionResult.style.color = "#721c24";
  }
});

// API Key save/load
saveApiKeyBtn.addEventListener("click", async () => {
  const key = apiKeyInput.value.trim();
  if (!key) {
    showMessage("请输入 API 密钥", "error");
    return;
  }
  await chrome.storage.local.set({ apiKey: key });
  showMessage("API 密钥已保存");
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
loadFormAnswers();
loadNetworkingSettings();

// --- Networking Settings ---
const networkingEnabled = document.getElementById("networkingEnabled");
const networkingMaxPerSession = document.getElementById("networkingMaxPerSession");
const networkingPersonTypes = document.getElementById("networkingPersonTypes");
const msgRecruiter = document.getElementById("msgRecruiter");
const msgHiringManager = document.getElementById("msgHiringManager");
const msgEngineer = document.getElementById("msgEngineer");
const saveNetworkingBtn = document.getElementById("saveNetworkingBtn");

async function loadNetworkingSettings() {
  try {
    const data = await apiCall("GET", "/settings");
    networkingEnabled.checked = data.networking_enabled || false;
    networkingMaxPerSession.value = data.networking_max_per_session || 3;
    networkingPersonTypes.value = data.networking_person_types || "recruiter,hiring_manager";

    // Load custom messages from YAML config endpoint
    const messages = await apiCall("GET", "/connections/messages");
    if (messages?.recruiter) msgRecruiter.value = messages.recruiter;
    if (messages?.hiring_manager) msgHiringManager.value = messages.hiring_manager;
    if (messages?.engineer) msgEngineer.value = messages.engineer;
  } catch (error) {
    // Settings endpoint might not have networking fields yet, that's fine
    console.log("Networking settings not available yet:", error.message);
  }
}

saveNetworkingBtn.addEventListener("click", async () => {
  try {
    // Save main networking settings
    await apiCall("POST", "/settings", {
      networking_enabled: networkingEnabled.checked,
      networking_max_per_session: parseInt(networkingMaxPerSession.value),
      networking_person_types: networkingPersonTypes.value,
    });

    // Save custom messages
    const messages = {};
    if (msgRecruiter.value.trim()) messages.recruiter = msgRecruiter.value.trim();
    if (msgHiringManager.value.trim()) messages.hiring_manager = msgHiringManager.value.trim();
    if (msgEngineer.value.trim()) messages.engineer = msgEngineer.value.trim();

    if (Object.keys(messages).length > 0) {
      await apiCall("POST", "/connections/messages", messages);
    }

    // Also persist locally
    await chrome.storage.local.set({
      networkingSettings: {
        enabled: networkingEnabled.checked,
        maxPerSession: parseInt(networkingMaxPerSession.value),
        personTypes: networkingPersonTypes.value,
      },
    });

    showMessage("社交设置已保存");
  } catch (error) {
    showMessage("保存社交设置失败", "error");
  }
});

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

// Event delegation for dynamic buttons (module scope can't use inline onclick)
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  const id = parseInt(btn.dataset.id);
  if (action === "deleteFilter") deleteFilter(id);
  else if (action === "deleteResume") deleteResume(id);
});

// --- Form Answers ---
const FORM_ANSWER_FIELDS = [
  "phone_number", "email",
  "first_name", "last_name",
  "city", "state", "country", "zip_code",
  "linkedin_url", "website",
  "years_of_experience", "work_authorization",
  "sponsorship", "willing_to_relocate",
  "start_date", "salary_expectation",
  "degree", "school", "field_of_study", "gpa",
];

const saveFormAnswersBtn = document.getElementById("saveFormAnswersBtn");

async function loadFormAnswers() {
  try {
    const data = await apiCall("GET", "/form-answers");
    FORM_ANSWER_FIELDS.forEach((field) => {
      const input = document.getElementById(`fa_${field}`);
      if (input) input.value = data[field] || "";
    });
  } catch (error) {
    console.error("Error loading form answers:", error);
  }
}

saveFormAnswersBtn.addEventListener("click", async () => {
  try {
    const answers = {};
    FORM_ANSWER_FIELDS.forEach((field) => {
      const input = document.getElementById(`fa_${field}`);
      if (input) answers[field] = input.value;
    });
    await apiCall("POST", "/form-answers", answers);
    showMessage("表单答案已保存");
  } catch (error) {
    showMessage("保存表单答案失败", "error");
  }
});
