# asvz-enroll

Enrols you in an ASVZ lesson from the terminal, right now.

**New here? Follow the [step-by-step setup guide](SETUP-GUIDE.md)** to have your computer
enrol you every week by itself, on macOS, Windows or Linux. No programming knowledge needed.

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

## When the request is sent

Many computer clocks are a few seconds, sometimes half a minute, off. A request sent at the
opening second by such a clock can reach ASVZ before enrolment opens and be refused. So the app
sends the enrolment a random 35 to 55 seconds after the opening time, by your computer's clock.
That covers clocks up to 35 seconds behind.

You can start the app up to 10 minutes before enrolment opens: it logs in, then waits. Started
earlier than that, it stops with an error saying how early it was. To allow an earlier start,
set the number of minutes in `.env`, for example `ASVZ_EARLY_START_MINUTES=60`. The login stays
valid for 12 hours, so keep it well below 720. Started after the opening,
it waits only for whatever is left of the delay.

To run it every week, start it a couple of minutes before enrolment opens, for example with
cron (enrolment opening Tuesdays at 19:15, so start at 19:13):

```
13 19 * * 2 sh "$HOME/ASVZ-enrollment/scripts/enrol-weekly.sh" --lesson-id 777112
```

`scripts/enrol-weekly.sh` (macOS, Linux) and `scripts/enrol-weekly.bat` (Windows Task
Scheduler) find uv, run the app with the options you give them, and append everything to
`asvz.log` in your home folder. The [setup guide](SETUP-GUIDE.md) walks through it on each
system.

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
| `enrolment_timing.py` | The random 35–55 s delay after opening |
| `email_notification.py` | One email through Brevo |
| `models.py`, `errors.py` | The data and the failures |

The requests were worked out from the browser traffic; see `traffic-notes.md`.

## Development

```bash
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
```
