# learnenglish

A Flask application for practising English vocabulary and spelling with individual user accounts and CSV word banks.

## Setup

1. Create a Python virtual environment and install dependencies: `pip install -r requirements.txt`.
2. Generate a **new** random application secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
3. Set `FLASK_SECRET_KEY` to that value in your environment. Do not commit it. Do **not** reuse the formerly hardcoded key.
4. For local HTTP development only, set `DEV_INSECURE_COOKIES=1`. In production, leave it unset and serve through HTTPS.
5. Run `python quiz.py` (development only). Visit `http://127.0.0.1:5002`.

The default SQLite file lives in Flask's instance directory. Override `DATABASE_URL` for another database. `WORDS_ROOT` optionally overrides the individual users' vocabulary folder. Upload a UTF-8 CSV containing `Word,Meaning` headers.

## Authentication and request flow

- `POST /register` validates the username and password, stores a Werkzeug password hash and redirects to login.
- `POST /login` verifies the hash, creates a Flask-Login authenticated session and updates `lastlogin`.
- Flask signs the client-side session cookie using `FLASK_SECRET_KEY`; the cookie contains a user identifier, **not** the user's password or a JWT. The browser sends it with subsequent requests.
- `@login_required` protects all personal vocabulary, quiz, spelling, and logout routes; unauthorized users are redirected to `/login`.
- `POST /logout` removes the authenticated state and clears the session. All POST forms require a CSRF token.
- CSV files are scoped by authenticated user ID. Quiz/spelling selections are kept per browser session, rather than process-global variables.

## Migration from the original version

**Important: existing database passwords were stored as plaintext.** The rewritten login deliberately refuses to treat a plaintext value as a valid hash. Before switching existing users, securely reset their passwords and replace their stored values with `generate_password_hash(new_password)` using an authorized, carefully controlled administrative migration. Never publish or log the old passwords. Rotate the old hardcoded Flask secret and invalidate existing sessions.

Original vocabulary files were stored at `Wordsbank/<username>/wordsbank.csv`. New files are stored at `<WORDS_ROOT>/<numeric-user-id>/wordsbank.csv` (by default under `instance/words`). Back up and migrate each user's CSV to their corresponding numeric ID, or ask users to upload again. This separation deliberately prevents username-based path selection.

Existing accounts must be migrated; **do not run this as a drop-in production upgrade without backups and a migration plan.** There is currently no password-reset UI or automated account migration.

## Security and deployment

- Passwords are hashed using Werkzeug; never store plaintext passwords.
- Session cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` by default. Use HTTPS and appropriate reverse-proxy configuration in production.
- CSRF protection covers POST forms. Registration and login are rate limited per source IP.
- The default rate-limit store is in-memory and suitable only for local use. Configure a shared store such as Redis via `RATELIMIT_STORAGE_URI` for multi-worker deployments and install the matching client dependency.
- Set up HTTPS, a production WSGI server, database backups, dependency scanning and a secret manager before deployment.
- The file-size limit is 2 MB. Each accepted CSV replaces only the current user's vocabulary file.

## Tests

`pip install pytest` and run `pytest -q`.
