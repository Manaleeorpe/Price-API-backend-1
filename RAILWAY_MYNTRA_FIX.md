# Railway Myntra `/price` Fix

## Issue

The backend worked locally, but the live Railway URL returned this response for a Myntra product URL:

```json
{
  "error": "Page could not be fetched: request timed out"
}
```

The Railway service itself was healthy. `/openapi.json` returned `200 OK`, and Railway showed the deployment as `SUCCESS`.

## Root Cause

There were two related problems:

1. The app was timing out while fetching Myntra from Railway.
   - The original fetch timeout was `15` seconds.
   - Railway logs showed each failing `/price` request took about `15s`, matching the timeout in `urlopen(..., timeout=15)`.
   - This meant the timeout was coming from the app's outbound request to Myntra, not from Railway routing.

2. Myntra does not expose the product price in the JSON-LD structure that the original parser expected.
   - The original API only searched `<script type="application/ld+json">` blocks.
   - For the tested Myntra page, the price was stored in embedded page state under `window.__myx`, inside fields like `discountedPrice`.

## Fix

The backend was updated to:

- Increase the page fetch timeout from `15` seconds to `30` seconds.
- Send more browser-like request headers when fetching product pages.
- Add a fallback parser for Myntra-style embedded product data in `window.__myx`.
- Keep the existing JSON-LD parser as the first/default extraction path.
- Add tests for the embedded Myntra price fallback.

## Verification

The fix was deployed to Railway successfully.

Live API URL:

```text
https://price-finder-backend-production-e613.up.railway.app/price
```

Test payload:

```json
{
  "Url": "https://www.myntra.com/trousers/arrow/arrow-men-checked-tapered-fit-trousers/39368038/buy"
}
```

Live response after the fix:

```json
{
  "Price": "1499"
}
```

Local tests also passed:

```text
Ran 8 tests
OK
```
