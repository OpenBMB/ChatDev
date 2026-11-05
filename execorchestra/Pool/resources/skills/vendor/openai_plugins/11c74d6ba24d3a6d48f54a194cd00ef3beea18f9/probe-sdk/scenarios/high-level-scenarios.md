# Probe SDK High-Level Scenarios

## 1) Meeting Pre-Join Readiness Gate

- Run Probe diagnostics before showing Meeting SDK join button.
- Block join for severe failures (no media permissions, fatal network score).
- Show guidance and retry path for recoverable failures.

## 2) Video Session Quality Predictor

- Pair Probe results with Video SDK session UX.
- Choose default video quality and renderer path based on capability checks.
- Fall back to audio-first profile when network quality is poor.

## 3) Support/Triage Diagnostic Capture

- Collect final diagnostic report for helpdesk workflows.
- Attach report to support ticket to reduce reproduction time.
- Compare report against known-good baseline by browser/OS cohort.

## 4) Managed Device Certification

- Run automated checks across approved browser/device matrix.
- Persist pass/fail score and feature support profile.
- Use certification output to guide endpoint policy and rollout.

## 5) Incident Response Validation

- During outage/performance alerts, run Probe tests from affected geos.
- Distinguish local device failures from Zoom/service-zone path issues.
- Route incident response based on network and protocol-specific findings.
