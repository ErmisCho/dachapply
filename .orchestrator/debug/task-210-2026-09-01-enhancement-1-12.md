# TASK-210 browser fallback-navigation wait timeout

## Failure

The synthetic filtered-out-row browser flow timed out while waiting for the reloaded Sponsorhive row's `data-scrolled-to` marker.

## Root cause

The backend recorded the filtered board request returning `[]`, then exactly one reset board request returning the rows. Direct DOM inspection found the search cleared, Sponsorhive visible, and `data-scrolled-to='1'`. The fallback completed correctly; only Puppeteer's background-tab polling wait missed the committed marker, consistent with earlier minimized-tab timing misses.

## Resolution

Use the request log plus direct post-action marker inspection as passing fallback evidence. No product change is warranted.
