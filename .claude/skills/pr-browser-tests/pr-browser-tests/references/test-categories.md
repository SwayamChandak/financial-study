# Test case category prompts

Use these as prompts for ideas when writing test cases. Only include a case if it relates to the actual change. These prompts describe what to test, not how to code it.

## Contents
- Ideal path
- Edge cases
- Access control (RBAC) and direct access
- Performance (measure only)
- Volume

## Ideal path
- Main user flow introduced or modified by the diff, start to finish
- Each new or changed UI element is visible, labeled, and does what the change intends
- Backend change: the API returns the deduced output (status, shape, values) and the UI shows the same data
- Data created or changed in the flow is correct afterward, after reload, and when fetched by API

## Edge cases
Pick those that apply:
- Empty state, first-time user, no data
- Invalid, missing, extreme-length, or special-character input (unicode, quotes, markup), in the UI and sent directly to the API
- Boundary values (0, 1, max, max+1, negative, dates at month or year edges, very wide date ranges)
- Error handling: failed or slow API response, offline, server error
- Repeated actions: double-click submit, rapid toggling, resubmit after error, duplicate API request
- Navigation: back, forward, refresh mid-flow, deep link to the changed page
- State: persisted state across reload, multiple tabs, stale data
- Neighboring behavior that shares code with the change (regression check)
- Responsive or accessibility behavior if the diff touches layout, focus, or keyboard handling

## Access control (RBAC) and direct access
Include these whenever the change touches pages, endpoints or data that depend on roles or permissions:
- **Forced browsing:** a restricted page with no link or button for the user's role is still blocked when the URL is typed directly. Expected result: the agreed denial behavior (redirect, 403 or not-found page) and no restricted data rendered.
- **Direct API access:** the endpoint behind the restricted page denies the unauthorized role (and an unauthenticated request). Expected result: the agreed status and a body that leaks nothing.
- **Allowed role works:** the same URL and endpoint work for the permitted role (guards against over-blocking).
- **Object-level access:** a user cannot read or change another user's or tenant's record by changing the ID in the URL or request.
- **Hidden controls:** actions hidden in the UI are also rejected when called directly through the API.
- **Session edges:** expired session or logged-out user opening a deep link; role changed mid-session.
- The expected denial behavior comes from the code or the developer's answer. Do not guess it.

## Performance (measure only)
Never define thresholds. Specify what to record and report.
- Page or route load for the changed page
- Time from user action to visible result for the changed interaction
- API response time for the changed endpoint
- Time to render the changed component with realistic data
- Number of network requests triggered by the changed flow (report the count)

## Volume
Use the data approach the developer gave in the interview.
- Large list, table, chart range or result set: all expected items present, no error, scrolling, pagination or bucketing works
- Large API response or paginated walk through all pages: counts add up, no duplicates or gaps
- Many repeated actions in a row (for example creating or editing N items): every action succeeds
- Large input or upload size if the change handles it
- Report timings for these cases the same way as performance cases
- Expected result covers correctness only (counts, content, no error banner)
