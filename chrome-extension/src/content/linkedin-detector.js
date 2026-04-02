/**
 * LinkedIn Job Page Detector
 * Detects when user views a job and offers to track it
 */

function detectJobListing() {
  // Extract job ID from LinkedIn URL: /jobs/1234567890/
  const url = window.location.href;
  const jobIdMatch = url.match(/\/jobs\/(\d+)\//);
  if (!jobIdMatch) return;

  const jobId = jobIdMatch[1];

  // Try multiple selectors for job title (LinkedIn changes DOM frequently)
  const titleSelectors = [
    ".job-details-jobs-unified-top-card__job-title h1",
    ".jobs-unified-top-card__job-title",
    ".t-24.t-bold.inline",
    "[data-qa='posted-in-module'] h1",
    ".jobs-details-top-card__job-title",
    "h1.topcard__title",
    "h1",
  ];
  let title = "Unknown Job";
  for (const selector of titleSelectors) {
    const el = document.querySelector(selector);
    if (el?.textContent?.trim()) {
      title = el.textContent.trim();
      break;
    }
  }

  // Send to service worker using correct payload format
  chrome.runtime.sendMessage(
    {
      action: "apiCall",
      payload: {
        endpoint: "/jobs",
        method: "POST",
        body: {
          linkedin_job_id: jobId,
          title: title,
          job_url: url,
        },
      },
    },
    (response) => {
      if (response?.success) {
        console.log("Job tracked:", jobId);
      }
    }
  );
}

// Run on page load
detectJobListing();

// Listen for SPA navigation via page-observer's custom event
window.addEventListener("linkedinPageChanged", () => {
  detectJobListing();
});
