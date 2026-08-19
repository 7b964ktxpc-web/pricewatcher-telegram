# Release Candidate Checklist

## User launch

- [ ] CI is green on `main`.
- [ ] Docker image builds successfully.
- [ ] Parser `/health` is healthy.
- [ ] Parser `/api/readiness` reports ready.
- [ ] Telegram bot token passes `getMe`.
- [ ] `/start` responds for a normal user.
- [ ] Text product search returns real offers.
- [ ] Photo search returns real offers.
- [ ] Watchlist add/remove works.
- [ ] Price checker updates prices.
- [ ] Price-drop notification reaches the user.
- [ ] Non-admin users cannot access admin actions.

## Release rule

Do not add new product features until every item above is verified in the production environment.
