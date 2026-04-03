/**
 * LinkedIn Job Page Detector
 * Detects when user views a job and offers to track it
 */

function detectJobListing() {
  const url = window.location.href;
  const jobIdMatch = url.match(/\/jobs\/(\d+)\//);
  if (!jobIdMatch) return;

  const jobId = jobIdMatch[1];

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
      // Job tracked - no logging to host page console
    }
  );
}

detectJobListing();

window.addEventListener("linkedinPageChanged", () => {
  detectJobListing();
});
