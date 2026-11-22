# Enrol automatically every week: step-by-step guide

Easiest: use the setup tool at https://danyk20.github.io/ASVZ-enrollment/

This guide sets up your computer so that it enrols you in your ASVZ class every week, on
its own, the moment enrolment opens. You don't need to know programming: you copy commands,
paste them and press Enter.

It takes about 20 minutes. Do the steps in order and don't skip any.

**At the end you will have:**

- your computer enrolling you every week by itself
- a log file showing what happened each time
- optionally, an email after every attempt with a link to cancel

**You need:**

- an ASVZ membership
- your **SWITCH edu-ID** email and password. If your login asks for a code from an app or an
  SMS, this app cannot log in for you.
- a computer (macOS, Windows or Linux) that is **switched on, awake and connected to the
  internet** at the moment enrolment opens. If it sleeps or is off, nothing happens that week.

> **Important: ASVZ's no-show rule.** If you are enrolled and don't come, ASVZ gives you a
> reminder, then a warning, and the third time it blocks you from all ASVZ sport for 8 days.
> The app enrols you **every** week. When you can't go, cancel before the cancellation
> deadline: open the lesson page (the link is in the email) and cancel there.

---

## Part 1: Find your lesson and when enrolment opens

Do this part first, whichever computer you have. Write down the three things it asks for.

### 1.1 Find the lesson id

1. Open the ASVZ timetable: <https://www.asvz.ch/426-sportfahrplan>
2. Find your class and click on it until you see the lesson page with the big title, the
   date, the room and an enrolment button.
3. Look at the address bar of your browser. It looks like this:

   ```
   https://schalter.asvz.ch/tn/lessons/777113
   ```

4. The number at the end is the **lesson id**. In this example: `777113`.

✍️ Write down: **lesson id** = `777113`

Any date of your weekly class works, even one in the past: the app always moves on to the
next upcoming one.

### 1.2 Find when enrolment opens

On the same lesson page, find the line **Einschreibezeitraum** (in English: "Enrollment
period"). It looks like this:

```
Einschreibezeitraum
Di, 24.11.2026 19:15 - Mi, 25.11.2026 19:15
```

The part **before the dash** is when enrolment opens. Here: **Tuesday at 19:15**.

The weekday is in German:

| German | Mo | Di | Mi | Do | Fr | Sa | So |
|---|---|---|---|---|---|---|---|
| English | Monday | Tuesday | Wednesday | Thursday | Friday | Saturday | Sunday |

> Careful: enrolment often opens on a **different day** than the class itself. In the
> example the class is on Wednesday, but enrolment opens on Tuesday. Always use the day
> **before the dash**.

### 1.3 Choose the start time

Start the app **2 minutes before** enrolment opens. In the example: Tuesday at **19:13**.

Why 2 minutes early? The app logs in, waits for the opening and then sends the enrolment
35 to 55 seconds after the opening time. The wait makes it work even if your computer's
clock is a little off. (It may start up to 10 minutes early. Starting earlier than that ends
with a "too early" error.)

✍️ Write down: **weekday** = `Tuesday`, **start time** = `19:13`

Now go to the part for your computer:

- [Part 2A: macOS](#part-2a-macos)
- [Part 2B: Windows](#part-2b-windows)
- [Part 2C: Linux](#part-2c-linux)

---

## Part 2A: macOS

### A1. Open Terminal

Press **⌘ Command + Space**, type `Terminal`, press **Enter**. A window with text opens.
This is where you paste the commands below.

To paste: **⌘ Command + V**, then press **Enter**. Wait until the command has finished
(you see a new line ending in `%` or `$`) before you paste the next one.

### A2. Install uv (the tool that runs the app)

Paste this and press Enter:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

When it has finished, **close the Terminal window and open a new one** (step A1 again).
Then check it worked:

```bash
uv --version
```

✅ You should see something like `uv 0.13.8`. If you see `command not found`, close Terminal
and open it again once more.

### A3. Download the app

Paste this as **one** command. It downloads the app into a folder called `ASVZ-enrollment`
in your home folder:

```bash
curl -L -o ~/asvz.zip https://github.com/danyk20/ASVZ-enrollment/archive/refs/heads/main.zip && unzip -q ~/asvz.zip -d ~ && mv ~/ASVZ-enrollment-main ~/ASVZ-enrollment && rm ~/asvz.zip
```

> Leave the folder where it is. Do **not** move it into Documents, Desktop or Downloads:
> macOS doesn't allow scheduled tasks to read those folders, and the app would silently fail.

Go into the folder:

```bash
cd ~/ASVZ-enrollment
```

### A4. Enter your login

Create your settings file and open it:

```bash
cp .env.example .env && nano .env
```

A simple text editor opens inside Terminal. Use the **arrow keys** to move (the mouse
doesn't work here). Fill in the three lines after the `=` sign, with no spaces around it:

```
ASVZ_USERNAME=your.name@example.org
ASVZ_PASSWORD=YourPassword123
ASVZ_LESSON_ID=777113
```

- `ASVZ_USERNAME`: your SWITCH edu-ID email
- `ASVZ_PASSWORD`: your SWITCH edu-ID password. If it contains a space, `#` or `"`, put
  it in single quotes: `ASVZ_PASSWORD='my pass#word'`
- `ASVZ_LESSON_ID`: your lesson id from step 1.1

Save and close: press **Control + O**, then **Enter**, then **Control + X**.

This file stays on your computer only. Never send it to anyone.

### A5. Test the login

```bash
uv run asvz-enroll --check-login
```

The first time this takes a minute, because it downloads Python.

✅ You should see: `Login ok, token valid until 04:15.` (with another time).
❌ If you see an error, go to [If something goes wrong](#if-something-goes-wrong).

### A6. Schedule it every week

Open your list of scheduled tasks:

```bash
EDITOR=nano crontab -e
```

The same editor as in A4 opens, probably empty. If macOS asks whether Terminal may
administer your computer, click **OK**.

Paste this line (**⌘ Command + V**):

```
13 19 * * 2 sh "$HOME/ASVZ-enrollment/scripts/enrol-weekly.sh" --lesson-id 777113
```

Now change it to **your** values from Part 1. Only these four things:

```
13 19 * * 2 sh "$HOME/ASVZ-enrollment/scripts/enrol-weekly.sh" --lesson-id 777113
│  │      │                                                                  │
│  │      └ weekday as a number (see table below)                            └ your lesson id
│  └ hour (19 = 7 pm, use 24-hour time)
└ minute
```

| Weekday | Monday | Tuesday | Wednesday | Thursday | Friday | Saturday | Sunday |
|---|---|---|---|---|---|---|---|
| Number | `1` | `2` | `3` | `4` | `5` | `6` | `0` |

The two `*` stay as they are. More examples:

- Monday 07:58 → `58 7 * * 1 …`
- Thursday 12:03 → `3 12 * * 4 …`

Several classes? Add one line per class.

Save and close: **Control + O**, **Enter**, **Control + X**. Check it was saved:

```bash
crontab -l
```

✅ You should see your line.

### A7. Test the schedule (2 minutes)

Make sure the schedule really works before you rely on it. Look at the clock in the top
right corner of your screen and add a test line that runs **2 minutes from now**. If it is
now 16:20 on a Sunday:

```bash
EDITOR=nano crontab -e
```

Add a second line (minute `22`, hour `16`, `*` for "every weekday", and `--check-login`, so
it only tests the login):

```
22 16 * * * sh "$HOME/ASVZ-enrollment/scripts/enrol-weekly.sh" --check-login
```

Save and close (**Control + O**, **Enter**, **Control + X**). Wait 3 minutes, then:

```bash
cat ~/asvz.log
```

✅ You should see a date and `Login ok, token valid until …`.
❌ If the file doesn't exist or stays empty, see
[If something goes wrong](#if-something-goes-wrong).

**Now remove the test line again:** `EDITOR=nano crontab -e`, move to the test line, press
**Control + K** to delete it, then **Control + O**, **Enter**, **Control + X**.

### A8. Keep your Mac awake

A sleeping Mac does not run scheduled tasks, and it doesn't catch up afterwards.

1. Open **System Settings** → **Battery** (on a desktop Mac: **Energy**).
2. Click **Options…** and switch on **Prevent automatic sleeping on power adapter when the
   display is off**.
3. At the start time, keep your Mac **plugged in** with the **lid open**.

Also check **System Settings** → **General** → **Date & Time**: **Set time and date
automatically** must be on, and the time zone must be **Zurich** (or another city in
Central European time).

You're done. 🎉 Read [Every week](#every-week).

---

## Part 2B: Windows

### B1. Open PowerShell

Click the **Start** button, type `PowerShell`, click **Windows PowerShell**. A blue or black
window with text opens. This is where you paste the commands below.

To paste: **right-click** in the window (or **Ctrl + V**), then press **Enter**. Wait until
the command has finished (you see a new line ending in `>`) before you paste the next one.

### B2. Install uv (the tool that runs the app)

Paste this and press Enter:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

When it has finished, **close PowerShell and open it again** (step B1). Then check it
worked:

```powershell
uv --version
```

✅ You should see something like `uv 0.13.8`. If you see "is not recognized", close
PowerShell and open it again once more.

### B3. Download the app

Paste this as **one** command. It downloads the app into a folder called `ASVZ-enrollment`
in your user folder (`C:\Users\<your name>\ASVZ-enrollment`):

```powershell
Invoke-WebRequest https://github.com/danyk20/ASVZ-enrollment/archive/refs/heads/main.zip -OutFile $HOME\asvz.zip; Expand-Archive $HOME\asvz.zip $HOME; Rename-Item $HOME\ASVZ-enrollment-main ASVZ-enrollment; Remove-Item $HOME\asvz.zip
```

Go into the folder:

```powershell
cd $HOME\ASVZ-enrollment
```

### B4. Enter your login

Create your settings file and open it in Notepad:

```powershell
copy .env.example .env; notepad .env
```

Fill in the three lines after the `=` sign, with no spaces around it:

```
ASVZ_USERNAME=your.name@example.org
ASVZ_PASSWORD=YourPassword123
ASVZ_LESSON_ID=777113
```

- `ASVZ_USERNAME`: your SWITCH edu-ID email
- `ASVZ_PASSWORD`: your SWITCH edu-ID password. If it contains a space, `#` or `"`, put
  it in single quotes: `ASVZ_PASSWORD='my pass#word'`
- `ASVZ_LESSON_ID`: your lesson id from step 1.1

Save with **Ctrl + S** and close Notepad. (Don't use "Save as": it could rename the file to
`.env.txt`, and then the app can't find it.)

This file stays on your computer only. Never send it to anyone.

### B5. Test the login

In PowerShell:

```powershell
uv run asvz-enroll --check-login
```

The first time this takes a minute, because it downloads Python.

✅ You should see: `Login ok, token valid until 04:15.` (with another time).
❌ If you see an error, go to [If something goes wrong](#if-something-goes-wrong).

### B6. Schedule it every week

Windows uses **Task Scheduler** for this.

1. Click **Start**, type `Task Scheduler`, open it.
2. In the right-hand panel, click **Create Task…** (not "Create Basic Task").
3. Tab **General**:
   - **Name:** `ASVZ enrolment` (or your class name)
   - Leave **Run only when user is logged on** selected.
4. Tab **Triggers** → click **New…**:
   - **Begin the task:** `On a schedule`
   - Select **Weekly**
   - **Start:** today's date, and your **start time** from step 1.3, e.g. `19:13:00`
   - **Recur every** `1` weeks on: tick **your weekday** (e.g. Tuesday), nothing else
   - Make sure **Enabled** (at the bottom) is ticked → **OK**
5. Tab **Actions** → click **New…**:
   - **Action:** `Start a program`
   - **Program/script:** click **Browse…**, go to your user folder →
     `ASVZ-enrollment` → `scripts`, and choose **enrol-weekly** (`enrol-weekly.bat`)
   - **Add arguments:** `--lesson-id 777113` (with **your** lesson id)
   - **Start in:** `C:\Users\<your name>\ASVZ-enrollment` (with **your** Windows user name)
   - → **OK**
6. Tab **Conditions**:
   - Tick **Wake the computer to run this task**
   - Untick **Start the task only if the computer is on AC power**
7. Tab **Settings**:
   - Tick **Run task as soon as possible after a scheduled start is missed**
8. Click **OK**.

Several classes? Create one task per class.

### B7. Test the schedule

In Task Scheduler, click **Task Scheduler Library** on the left, find your task in the
list, **right-click** it and choose **Run**. A black window may flash briefly.

Wait a minute, then in PowerShell:

```powershell
type $HOME\asvz.log
```

✅ You should see a date and a line from the app. If enrolment isn't open yet, that line
is an error ending in `too early`: **that's fine**, it proves the task works. If you set up
email, you also get a "failed" email for this test. (If enrolment happens to be open right
now, this test really enrols you, just as the weekly run would.)
❌ If the file doesn't exist, see [If something goes wrong](#if-something-goes-wrong).

### B8. Keep your computer awake

1. Open **Settings** → **System** → **Power & battery** (Windows 10: **Power & sleep**).
2. Set **Sleep** (when plugged in) to **Never**.
3. At the start time, keep the computer **switched on and plugged in**. You must be logged
   in to Windows; a locked screen is fine.

Also check **Settings** → **Time & language** → **Date & time**: **Set time automatically**
must be on, and the time zone must be **(UTC+01:00) Amsterdam, Berlin, Bern, …**.

You're done. 🎉 Read [Every week](#every-week).

---

## Part 2C: Linux

These steps are for Ubuntu, Debian, Linux Mint and similar. Other distributions work the
same way; only the package commands differ.

### C1. Open a terminal

Press **Ctrl + Alt + T** (or open **Terminal** from your applications). Paste with
**Ctrl + Shift + V**, then press **Enter**.

### C2. Install uv and unzip

```bash
sudo apt install -y curl unzip cron
```

(It asks for your computer password; nothing appears while you type it, that's normal.)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Close the terminal and open a new one.** Then check:

```bash
uv --version
```

✅ You should see something like `uv 0.13.8`.

### C3. Download the app

Paste this as **one** command:

```bash
curl -L -o ~/asvz.zip https://github.com/danyk20/ASVZ-enrollment/archive/refs/heads/main.zip && unzip -q ~/asvz.zip -d ~ && mv ~/ASVZ-enrollment-main ~/ASVZ-enrollment && rm ~/asvz.zip
```

```bash
cd ~/ASVZ-enrollment
```

### C4. Enter your login

```bash
cp .env.example .env && nano .env
```

Fill in the three lines after the `=` sign, with no spaces around it (move with the arrow
keys):

```
ASVZ_USERNAME=your.name@example.org
ASVZ_PASSWORD=YourPassword123
ASVZ_LESSON_ID=777113
```

If your password contains a space, `#` or `"`, put it in single quotes:
`ASVZ_PASSWORD='my pass#word'`

Save and close: **Ctrl + O**, **Enter**, **Ctrl + X**.

### C5. Test the login

```bash
uv run asvz-enroll --check-login
```

✅ You should see: `Login ok, token valid until 04:15.` (with another time).

### C6. Schedule it every week

```bash
crontab -e
```

If it asks you to choose an editor, type the number next to `nano` and press **Enter**.
Go to the very end of the file with the arrow keys and paste:

```
13 19 * * 2 sh "$HOME/ASVZ-enrollment/scripts/enrol-weekly.sh" --lesson-id 777113
```

Change the minute, hour, weekday number and lesson id to your values, exactly as explained
in [step A6](#a6-schedule-it-every-week) (the explanation and the weekday table are the
same). Save and close: **Ctrl + O**, **Enter**, **Ctrl + X**.

Check that cron is running:

```bash
systemctl is-active cron
```

✅ You should see `active`. (On Fedora the service is called `crond`:
`sudo dnf install cronie` and `sudo systemctl enable --now crond`.)

### C7. Test the schedule

Exactly like [step A7](#a7-test-the-schedule-2-minutes): add a test line 2 minutes in the
future with `--check-login`, wait, run `cat ~/asvz.log`, then delete the test line again.

### C8. Keep your computer awake

Open **Settings** → **Power** and switch **Automatic Suspend** off (at least when plugged
in). Check that the time zone is **Europe/Zurich**:

```bash
timedatectl
```

You're done. 🎉

---

## Every week

- The app runs by itself at your start time. You don't need to open anything.
- **Check the result:** in the email (if you set it up), or in the log file:
  - macOS and Linux: `cat ~/asvz.log`
  - Windows: `type $HOME\asvz.log` in PowerShell
- A successful week looks like this:

  ```
  ===== Tue Dec  1 19:13:00 CET 2026 =====
  Lesson 777113 is over; using the upcoming lesson 777114.
  Enrolment opens 19:15:00; waiting until 19:15:47 in case this computer's clock is behind.
  Enrolled: Manege: Akrobatik, Wed 02 Dec 2026 19:15, place 3.
  Request sent 19:15:47 by this computer's clock, 47.2 seconds after enrolment opened.
  ```

- **Can't go?** Cancel on the lesson page before the deadline (the line *Abmeldefrist* on the
  lesson page). See the no-show rule at the top.
- **New semester:** when the weekly series ends, the log (and the email) says
  `The series has probably ended`. Find the new lesson id (Part 1) and replace the old number
  in `.env`, your crontab line, or your Windows task.

## Email after every attempt (optional)

The app can email you the result of every attempt, with a link to the lesson page. It uses
[Brevo](https://www.brevo.com), which is free for this.

1. Create a free account at <https://www.brevo.com>.
2. In Brevo, open **Senders, Domains & Dedicated IPs** → **Senders** and add your email
   address as a sender. Brevo sends you a confirmation email; click the link in it.
3. In Brevo, open **SMTP & API** → **API keys** → **Generate a new API key**. Copy the key
   (it starts with `xkeysib-`).
4. Open your settings file again (macOS/Linux: `nano ~/ASVZ-enrollment/.env`, Windows:
   `notepad $HOME\ASVZ-enrollment\.env`) and fill in:

   ```
   ASVZ_EMAIL_RECIPIENT=your.name@example.org
   BREVO_API_KEY=xkeysib-...
   BREVO_SENDER_EMAIL=the-address-you-added-in-step-2@example.org
   ```

5. Save. From now on every attempt sends an email. If it doesn't arrive, look in your spam
   folder.

## Stop or change the weekly enrolment

- **macOS and Linux:** run `EDITOR=nano crontab -e`. Delete the line with **Control + K**
  (or change it), then **Control + O**, **Enter**, **Control + X**.
- **Windows:** open Task Scheduler → **Task Scheduler Library**, right-click your task and
  choose **Disable** (pause), **Delete** (stop for good) or **Properties** (change).

## If something goes wrong

First look at the log file (see [Every week](#every-week)). Find the message in this table:

| What you see | What it means | What to do |
|---|---|---|
| The log file doesn't exist or has no new entry | The task didn't run | The computer was asleep or off, the weekday or time in your schedule is wrong, or (macOS) the folder is in Documents/Desktop/Downloads. Check those, then repeat the schedule test (A7, B7 or C7). |
| `Missing: ASVZ_USERNAME, …` | The app can't find your settings | The file must be called exactly `.env` and be inside the `ASVZ-enrollment` folder. Windows: check that it isn't called `.env.txt`. |
| `SWITCH edu-ID did not accept the username or password` | Wrong login | Fix `ASVZ_USERNAME` / `ASVZ_PASSWORD` in `.env`. Test with the step "Test the login". |
| `SWITCH edu-ID showed a page this app cannot answer` or `ASVZ wants an extra step` | Your account needs something only a person can do | Log in once in your browser at <https://schalter.asvz.ch/tn/>, accept whatever it asks, then test again. If it asks for a code every time, this app can't log in for you. |
| `… too early. The app waits for the opening only if it is at most 0:10:00 away` | The task started more than 10 minutes before enrolment opens | Check the weekday and time in your schedule against Part 1. |
| `… closed … too late` | The task started after enrolment closed | Same: check weekday and time. |
| `ASVZ refused the enrolment (HTTP …)` | ASVZ said no, often because the class is full | Read ASVZ's message after it. If the class fills in seconds, there is nothing more the app can do. |
| `The series has probably ended` | The weekly class has no more dates | Find the new lesson id (Part 1) and update it. |
| `uv was not found` or `uv is not recognized` | uv is missing | Repeat the step "Install uv", then close and reopen the terminal. |
| `Network problem: …` | No internet at that moment | Check the computer's connection, e.g. Wi-Fi in sleep mode. |
