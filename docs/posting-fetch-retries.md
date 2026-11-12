# Automatic posting-fetch retries

An unchanged job's failed automatic lookup is reused for up to **10 minutes** across analysis and document generation. The failure message and actual last-check time are retained. This cooldown does not schedule a fetch by itself: the next automatic attempt after it expires may fetch again.

To retry immediately, use **Retry** on the Queue or **Fetch posting text** on the job page. A changed URL or accepted text has a separate retrieval identity. Pending **Keep current / Use fetched** choices are never replaced by automatic lookups, and an owner edit/check arriving during a fetch wins over its stale result.

Equivalent in-flight automatic lookups share one network call. At most 256 entries are held; completed entries may be evicted sooner under load. The local single-process worker's cache clears on restart. Before moving automatic fetch work to multiple processes, replace process-local coalescing with a shared lease; existing SSRF/network guards remain unchanged.

Hermetic regression command (from `backend/`):

```sh
uv run pytest -q jobradar/tests/test_posting_fetch_cooldown.py jobradar/tests/test_link_only_prep.py jobradar/tests/test_posting_fetch.py jobradar/tests/test_posting_completeness.py jobradar/tests/test_api.py::test_cv_worker_retries_missing_posting_text_before_generation
```
