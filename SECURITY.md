# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private
vulnerability reporting for this repository, or contact the maintainer through GitHub,
with steps to reproduce and the expected impact.

## Configuration and secrets

- All configuration is read from environment variables. `.env.example` and
  `frontend/.env.example` contain placeholders only; real `.env` files are git-ignored.
- Never commit database connection strings that include credentials, OAuth secrets or
  API keys. If one is committed by mistake, rotate it immediately; removing it from the
  latest commit does not remove it from git history.

Sensitive variables: `MONGO_URI` / `MONGODB_URI` (may contain credentials), `AUTH_SECRET`,
`AUTH_GOOGLE_SECRET`, `LLM_API_KEY`, and AWS credentials if SageMaker is used.

## Known limitations

- The user-data endpoints (`/push-user`, `/get-users`, `/delete-user/<id>`,
  `/get-user-conditions`, `/get-user-condition/<id>`) require a shared `ADMIN_TOKEN`
  (`Authorization: Bearer ...`) and are disabled when it is unset. Only the Next.js server
  sends it; never expose it to the browser.
- The remaining endpoints (prediction, schedule, weather, chat, soil lookup) are open and
  not rate limited. Keep the API on a private network or behind a proxy that adds both.
- The `.joblib` model file is a pickle. Only load model artifacts you trained yourself or
  obtained from a trusted source.
