# Easy Apply Single-Job Stabilization Design

Date: 2026-04-25
Status: Approved
Scope: Phase A only

## 1. Goal

Stabilize a single LinkedIn Easy Apply transaction before attempting broader batch automation.

The target outcome for Phase A is a deterministic single-job flow:

1. Open a specific job
2. Open Easy Apply
3. Detect the active Easy Apply modal only
4. Fill only fields inside that modal
5. Advance through steps reliably
6. Reach the submit state in dry-run mode and intercept before the real submit click
7. Cleanly dismiss the modal and restore the page to a clickable state
8. After dry-run stability is proven, allow controlled real submission for the same job class

This phase is explicitly designed to fix transaction stability, not throughput.

## 2. Why This Phase Exists

The current system already proves that full automation is not zero, but it is not stable enough to be trusted.

Observed evidence from the current project state:

- The automation successfully applied to `BeaconFire Inc. / Java Software Engineer` on 2026-04-21.
- The same session finished with only `1 applied out of 21 jobs`, which means the user's real problem is low reliability, not total absence of automation.
- Repeated failures show the form filler interacting with background page fields such as `City, state, or zip code` while an Easy Apply modal is open.
- Repeated overlay interception errors show that the modal or success overlay is not always cleaned up before the next action.
- The `Turing / Remote Senior JavaScript/React Engineer – AI Training (US-based)` sample failed with both step-progression and field-validation errors, proving that the single-transaction logic is still unstable.

The correct shortest path is therefore to stabilize one Easy Apply transaction end to end before expanding back to batch mode or post-apply networking.

## 3. Phase A Scope

### In scope

Phase A fixes only the single-job Easy Apply transaction:

- job entry and sample targeting
- Easy Apply modal detection and scoping
- field detection and filling inside the modal only
- step validation before advancing
- `Next`, `Review`, and `Submit` detection inside the modal footer
- dry-run submit interception
- post-submit or post-dry-run cleanup
- structured failure reporting for this transaction
- repeatable validation against fixed sample jobs

### Out of scope

Phase A does not include:

- multi-page batch stability
- generalized support for every LinkedIn form variant
- recruiter connection automation
- networking message workflows
- search/filter strategy redesign
- large-scale architecture refactors unrelated to Easy Apply transaction stability

## 4. Design Principles

1. Treat one Easy Apply run as a transaction with explicit boundaries.
2. Never scan or interact with the full page when a modal is active.
3. Prefer deterministic failure over unsafe guessing.
4. Do not advance steps while required fields remain unresolved.
5. Do not continue to the next job until overlays are confirmed cleared.
6. Use dry-run as a formal submission-readiness checkpoint, not as a loose simulation.

## 5. Success Criteria

### Phase A safety validation

Phase A is considered dry-run stable when the fixed sample job can:

- reach the real `Submit application` state three consecutive times
- intercept before the real submit click when `dry_run=true`
- produce zero unresolved required fields
- produce zero dominant overlay/background-field failures
- cleanly dismiss the modal and leave the page clickable after each run

### Phase A controlled real-submit validation

After dry-run passes, Phase A is considered submit-ready when a sample job class can:

- complete two consecutive real submissions
- record `applications.status = applied`
- avoid the known dominant failures:
  - background field interaction
  - overlay interception after submit
  - vague progression failure such as `could not proceed`

## 6. Failure Criteria

Phase A remains incomplete if any of the following still occurs:

- background page fields are scanned or filled while the modal is open
- the modal root is ambiguous or not isolated
- unresolved required fields exist when trying to advance
- footer action detection depends on broad full-page button matching
- the overlay remains active after submit or dismiss
- the same sample produces inconsistent results across repeated runs

## 7. Proposed Architecture Changes

### 7.1 Introduce `EasyApplySession`

A new transaction object becomes the runtime boundary for one Easy Apply flow.

Responsibilities:

- locate and hold the active modal root
- track current step state
- expose only the fields inside the active step
- expose only modal-scoped footer actions
- store resolved fields, unresolved fields, and validation errors
- perform final cleanup and overlay verification

This session object is the core change for Phase A. Without it, modal and background DOM continue to leak into each other.

### 7.2 Narrow `easy_apply.py` to flow orchestration

`backend/app/automation/easy_apply.py` stops behaving like a page-wide selector script.

Its new responsibility is orchestration only:

- open Easy Apply
- create an `EasyApplySession`
- iterate `fill_step -> validate_step -> advance_step`
- intercept at submit when `dry_run=true`
- invoke cleanup
- return a structured result object

It must not use broad page-wide selectors as its primary source of truth for `Next`, `Review`, or `Submit`.

### 7.3 Convert `form_filler.py` into a modal-scoped resolver

`backend/app/automation/form_filler.py` must operate on a provided modal root only.

Its responsibilities become:

- enumerate visible and editable fields inside the modal only
- skip disabled, hidden, or background elements
- classify fields before filling them
- return explicit unresolved fields instead of guessing

Minimum field classes for Phase A:

- text inputs
- numeric inputs
- select dropdowns
- radio groups, including `Yes/No`
- checkboxes
- file uploads

### 7.4 Add step validation before step advancement

A dedicated validation step is required before each `Next`, `Review`, or `Submit` action.

Validation checks:

- are there unresolved required fields?
- are there visible validation errors?
- what is the actual primary footer action for this step?
- is the modal still active and interactive?

If validation fails, the transaction stops with a structured failure instead of attempting a blind click.

### 7.5 Make cleanup a first-class step

Cleanup must become its own required phase after dry-run interception or real submit.

Cleanup responsibilities:

- detect success modal or completion dialog
- click `Done`, `Dismiss`, or equivalent completion action
- wait for overlay disappearance
- confirm that the page underneath is clickable again
- mark cleanup success or cleanup failure explicitly

The automation must not move to the next job until cleanup succeeds.

## 8. Data Flow

### Phase A transaction flow

1. Select fixed sample job
2. Open job detail
3. Open Easy Apply
4. Create `EasyApplySession`
5. Collect active step fields from modal root
6. Resolve and fill supported fields
7. Validate step
8. Detect primary footer action
9. Advance to next step or review
10. If action is `Submit` and `dry_run=true`, intercept and mark `submit-ready`
11. Run cleanup
12. Record structured outcome

### Result payload requirements

Each transaction result must include at least:

- `job_id`
- `job_title`
- `company`
- `steps_completed`
- `resolved_fields`
- `unresolved_fields`
- `validation_errors`
- `final_action`
- `cleanup_success`
- `success`
- `failure_type`

## 9. Error Handling Design

### 9.1 Replace vague failures with structured failure types

The flow must stop classifying failures as generic step errors.

Minimum failure types for Phase A:

- `modal_not_found`
- `field_unresolved`
- `field_validation_failed`
- `advance_button_not_found`
- `overlay_not_cleared`
- `submit_intercepted_dry_run`
- `submit_failed`

### 9.2 Unresolved fields must block advancement

If a required field cannot be safely resolved, the system must stop rather than guess.

This is especially important for the currently observed failure patterns:

- `Select an option`
- `Please enter a valid answer`
- `Enter a decimal number larger than 0.0`

Short-term visible success may decrease, but diagnostic accuracy and long-term stability increase.

### 9.3 Dry-run becomes a hard checkpoint

Dry-run success means only one thing: the transaction reached a real submit-ready state.

Dry-run is not counted as successful simply because no exception occurred. It passes only if:

- all required fields are resolved
- no active validation errors remain
- the detected primary footer action is the real submit action
- cleanup succeeds after interception

## 10. Testing Strategy

### 10.1 Fixed regression samples

Phase A uses a fixed small sample set instead of batch coverage.

Primary sample:

- `Turing / Remote Senior JavaScript/React Engineer – AI Training (US-based)`

Safety-regression sample:

- `BeaconFire Inc. / Java Software Engineer`

These samples cover both a known failure class and a known simpler success class.

### 10.2 Acceptance sequence

Dry-run validation:

- run the primary sample three consecutive times in dry-run mode
- each run must reach submit-ready state
- each run must cleanly close the modal

Real-submit validation:

- run a controlled real-submit flow twice for the approved sample class
- both runs must store `applied`
- neither run may leave overlay interference behind

### 10.3 What not to use as the main test for Phase A

The following is explicitly not the primary validation strategy:

- one large batch run across many jobs
- multi-page throughput counts
- success judged only by session summary

That would hide the exact instability Phase A is trying to remove.

## 11. Logging and Observability

For each Phase A transaction, log the following:

- session id
- sample job identifier
- modal root detection result
- step index
- detected footer action
- resolved fields
- unresolved fields
- visible validation errors
- final action
- cleanup success
- failure type

The system must make a failed run replayable from logs without requiring guesswork.

## 12. Rollout Plan

### Step 1

Refactor the Easy Apply flow around modal-scoped session boundaries.

### Step 2

Get the fixed failure sample to pass dry-run three consecutive times.

### Step 3

Verify the known simpler sample still works and has not regressed.

### Step 4

Enable controlled real submit for the approved sample class.

### Step 5

Only after all of the above, reopen the question of multi-job stabilization and recruiter connection automation.

## 13. Risks and Constraints

- LinkedIn DOM changes remain a constant external risk.
- Some field types may still require future expansion beyond Phase A.
- Real-submit verification must be used carefully to avoid accidental duplicate applications.
- The current repository already contains many unrelated in-progress changes, so implementation should minimize cross-cutting edits.

## 14. Decision Summary

The approved Phase A decision is:

- fix single-job Easy Apply stability first
- validate with dry-run before real submit
- isolate all interactions to the active modal
- block unsafe guesses on unresolved fields
- require deterministic cleanup before continuing

This spec intentionally optimizes for reliability and diagnosability over speed or feature breadth.
