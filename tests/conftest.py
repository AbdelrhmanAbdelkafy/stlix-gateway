"""Test-wide environment.

The gateway rate-limits per client IP (120/min by default). Under pytest every
request in the whole suite comes from the same client — `testclient` — into the
same in-memory fixed window, so the suite as a whole eats one user's minute.
It sat just under the limit for a while and then a handful of new routes pushed
it over, and four unrelated files started failing with 429: a test failure that
says nothing about the code under test and moves depending on what else ran.

So the limiter is off for tests, set before anything imports `app`. Nothing here
asserts on 429; if a test is ever written for the limiter itself, it should build
its own app with `RateLimitMiddleware` rather than lean on the global setting.
"""
import os

os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")
