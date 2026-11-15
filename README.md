# asvz-enroll

Enrols you in an ASVZ lesson from the terminal, right now.

## Setup

```bash
brew install uv
```

```bash
uv sync
```

```bash
cp .env.example .env
```

Fill in `.env` (it is ignored by git):

```
ASVZ_USERNAME=your-edu-id-email
ASVZ_PASSWORD=your-edu-id-password
ASVZ_LESSON_ID=781265
```

The lesson id is the number at the end of `https://schalter.asvz.ch/tn/lessons/<number>`.
Every date of a weekly lesson has its own id, one higher each week.

You can leave an old id in `.env`: if that lesson is already over, the app moves to the next
upcoming lesson of the same weekly series. A lesson that started 10 days ago is two weeks
back, so the app uses the id plus 2. It checks that the lesson found there has the same
sport, title, weekday and time, and stops with an error if not (for example when the
semester's series has ended).

## Use

Everything from `.env`:

```bash
uv run asvz-enroll
```

Another lesson, login from `.env`:

```bash
uv run asvz-enroll --lesson-id 781265
```

Everything on the command line (the password then lands in your shell history):

```bash
uv run asvz-enroll --username me@example.org --password 'secret' --lesson-id 781265
```

Only test the login, without enrolling:

```bash
uv run asvz-enroll --check-login
```

## Email about the result

Add these to `.env` to get an email after every enrolment attempt, whether it succeeded or failed:

```
ASVZ_EMAIL_RECIPIENT=you@example.org
BREVO_API_KEY=xkeysib-...
BREVO_SENDER_EMAIL=an-address-verified-in-brevo@example.org
```

The email is sent through [Brevo](https://www.brevo.com) (the free plan is enough). Create the
API key under "SMTP & API" → "API keys"; the sender must be a verified sender in your Brevo
account. Without `ASVZ_EMAIL_RECIPIENT` no email is sent. If the email cannot be sent, the app
prints a warning and the exit code still describes the enrolment.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Enrolled, or already enrolled |
| 1 | Enrolment not possible (unknown lesson, window not open, refused by ASVZ) |
| 2 | Username, password or lesson id missing or invalid |
| 3 | Login failed |
| 4 | Network problem |

## How it works

Read `src/asvz_enroll/cli.py` first; it is the whole story in a few lines.

| File | Job |
|---|---|
| `cli.py` | Command line: read options, log in, enrol, report |
| `settings.py` | Options first, `.env` second |
| `login.py` | The six steps of the SWITCH edu-ID login |
| `pkce.py`, `html_forms.py` | Helpers for the login |
| `lesson_api.py` | The three ASVZ API calls |
| `upcoming_lesson.py` | From a past lesson id to the next upcoming one |
| `email_notification.py` | One email through Brevo |
| `models.py`, `errors.py` | The data and the failures |

The requests were worked out from the browser traffic; see `traffic-notes.md`.

## Development

```bash
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
```
