---
id: TASK-341
title: Workday postings keep their headings and bullet lines
status: To Do
assignee: []
created_date: '2026-10-22 08:39'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 341000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-22 (screenshot of zuehlke.wd3.myworkdayjobs.com Advanced Data Engineer, job 1533): 'this job listing should be able to get the whole text, the whole jd is visible'. Measured: fetch_posting_text returns all 6,914 characters but flattened into 5 lines -- 'The role', 'How you'll make an impact', 'What's important to us', 'What we offer' and every bullet are run into paragraphs, so the job page's structured version reports 'no recognisable sections'. Workday's public job endpoint https://<tenant>.wdN.myworkdayjobs.com/wday/cxs/<tenant>/<site>/job/<path> returns jobPostingInfo.jobDescription as HTML with those headings and lists (measured: 6,737 chars, headings present).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A *.myworkdayjobs.com job link is read from Workday's cxs JSON endpoint (guarded download like the Cornerstone path) and its HTML turned into lines with headings and bullets kept
- [ ] #2 For job 1533's link the fetched text has the section headings on their own lines and the structured version finds sections
- [ ] #3 Locale-prefixed Workday URLs (/en-US/<site>/job/...) work; any failure falls back to today's path
- [ ] #4 The employer name from hiringOrganization (leading numeric code stripped) fills a placeholder company only
- [ ] #5 Tests use a recorded-shape fake response; no network in tests
<!-- AC:END -->
