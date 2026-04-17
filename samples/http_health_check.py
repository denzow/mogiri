"""HTTP health check sample for mogiri jobs.

Checks one or more URLs and reports their status.
Exits with error if any URL returns a non-2xx response or times out.

Required environment variables:
  CHECK_URLS  - Comma-separated list of URLs to check

Optional environment variables:
  CHECK_TIMEOUT  - Request timeout in seconds (default: 10)
"""

import json
import os
import sys
import urllib.request
from urllib.error import HTTPError, URLError


def check_url(url, timeout):
    """Check a URL and return (status_code, response_time_ms, error)."""
    import time

    start = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = (time.time() - start) * 1000
            return resp.status, elapsed, None
    except HTTPError as e:
        elapsed = (time.time() - start) * 1000
        return e.code, elapsed, str(e)
    except URLError as e:
        elapsed = (time.time() - start) * 1000
        return None, elapsed, str(e.reason)
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return None, elapsed, str(e)


def main():
    urls_raw = os.environ.get("CHECK_URLS", "")
    timeout = int(os.environ.get("CHECK_TIMEOUT", "10"))

    if not urls_raw.strip():
        print("Error: CHECK_URLS is required.", file=sys.stderr)
        sys.exit(1)

    urls = [u.strip() for u in urls_raw.split(",") if u.strip()]
    has_failure = False
    results = []

    for url in urls:
        status, elapsed_ms, error = check_url(url, timeout)
        ok = status is not None and 200 <= status < 300
        if not ok:
            has_failure = True

        result = {
            "url": url,
            "status": status,
            "time_ms": round(elapsed_ms, 1),
            "ok": ok,
        }
        if error:
            result["error"] = error

        label = "OK" if ok else "FAIL"
        status_str = str(status) if status else "N/A"
        print(f"[{label}] {url} - {status_str} ({elapsed_ms:.0f}ms)")
        if error:
            print(f"       Error: {error}")
        results.append(result)

    # Output JSON summary for chained jobs
    print(f"\n{json.dumps(results, indent=2)}")

    sys.exit(1 if has_failure else 0)


if __name__ == "__main__":
    main()
