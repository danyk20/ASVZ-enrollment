// DOM wiring for the setup tool. The logic lives in lesson.js.
import {
  DEFAULT_SITE_URL,
  ERROR_MESSAGES,
  buildCommand,
  detectPlatform,
  isPhoneOrTablet,
  fetchLesson,
  parseLessonLink,
  schedule,
} from "./lesson.js";
import {
  PHONE_VISIT_EVENT,
  classLabel,
  commandCopiedEvent,
  countEvent,
  lessonLookedUpEvent,
  startAnalytics,
  systemChosenEvent,
} from "./analytics.js";

const CHECK_DELAY_MS = 400;
const COPIED_MS = 2000;
const REPO_URL = "https://github.com/danyk20/ASVZ-enrollment";
const PLATFORM_NAMES = { macos: "macOS", windows: "Windows", linux: "Linux" };
const SCRIPT_URLS = {
  macos: `${REPO_URL}/blob/main/docs/setup.sh`,
  linux: `${REPO_URL}/blob/main/docs/setup.sh`,
  windows: `${REPO_URL}/blob/main/docs/setup.ps1`,
};
const INSTRUCTIONS = {
  macos: "Open <strong>Terminal</strong> (&#8984; Space, type Terminal), paste, press Enter.",
  windows: "Open <strong>PowerShell</strong> (Start, type PowerShell), paste, press Enter.",
  linux: "Open a terminal (Ctrl Alt T), paste, press Enter.",
};

const $ = (id) => document.getElementById(id);
const linkInput = $("lesson-link");
const statusBox = $("lesson-status");
const lessonCard = $("lesson-card");
const commandHint = $("command-hint");
const commandArea = $("command-area");
const commandText = $("command-text");
const instruction = $("instruction");
const copyButton = $("copy-button");
const scriptLink = $("script-link");
const detectedNote = $("detected-note");
const platformInputs = [...document.querySelectorAll('input[name="os"]')];

let platform = detectPlatform(navigator);
let current = null; // the schedule for the lesson that was found, or null
let currentLabel = ""; // that lesson's name for analytics, e.g. "Manege: Akrobatik (Wednesday 19:15)"
const countedSystems = new Set(); // "lessonId:platform" pairs already counted
let lookupId = 0;
let checkTimer = null;
let copyTimer = null;

function setStatus(text, kind = "") {
  statusBox.className = `lesson-status ${kind}`.trim();
  statusBox.replaceChildren();
  if (text) statusBox.append(text);
}

function showLoading() {
  statusBox.className = "lesson-status is-loading";
  const spinner = document.createElement("span");
  spinner.className = "spinner";
  spinner.setAttribute("aria-hidden", "true");
  statusBox.replaceChildren(spinner, document.createTextNode("Looking up your class…"));
}

function showError(code) {
  linkInput.setAttribute("aria-invalid", "true");
  setStatus(ERROR_MESSAGES[code] ?? ERROR_MESSAGES.network, "is-error");
  lessonCard.hidden = true;
  lessonCard.replaceChildren();
}

function paragraph(...parts) {
  const p = document.createElement("p");
  p.append(...parts);
  return p;
}

function bold(text) {
  const strong = document.createElement("strong");
  strong.textContent = text;
  return strong;
}

function renderLesson(lesson, info) {
  linkInput.removeAttribute("aria-invalid");
  setStatus("");

  const name = document.createElement("p");
  name.className = "lesson-name";
  name.textContent = lesson.title ? `${lesson.sportName}: ${lesson.title}` : lesson.sportName;

  const when = document.createElement("p");
  when.className = "lesson-when";
  const details = [
    `Every ${info.lessonWeekdayName}`,
    info.lessonTime,
    lesson.facility,
  ].filter(Boolean);
  when.textContent = details.join(" · ");

  const tip = document.createElement("span");
  tip.className = "info";
  tip.tabIndex = 0;
  tip.setAttribute("role", "img");
  tip.setAttribute("aria-label", "More information");
  tip.textContent = "ⓘ";
  const tipText = document.createElement("span");
  tipText.className = "tip";
  tipText.setAttribute("role", "tooltip");
  tipText.textContent = "2 minutes early, so it is logged in when enrolment opens.";
  tip.append(tipText);

  const startLine = paragraph("Your computer starts at ", bold(`${info.weekdayName} ${info.time}`), tip);

  lessonCard.replaceChildren(
    name,
    when,
    document.createElement("hr"),
    paragraph("Enrolment opens ", bold(`${info.opensWeekdayName} ${info.opensTime}`)),
    startLine,
  );
  lessonCard.hidden = false;
}

function renderCommand() {
  const ready = current !== null;
  commandHint.hidden = ready;
  commandArea.hidden = !ready;
  if (!ready) return;

  commandText.textContent = buildCommand(platform, current, DEFAULT_SITE_URL);
  countSystemOnce();
  instruction.innerHTML = INSTRUCTIONS[platform];
  scriptLink.href = SCRIPT_URLS[platform];
  copyButton.textContent = "Copy";
}

function countSystemOnce() {
  const key = `${current.lessonId}:${platform}`;
  if (countedSystems.has(key)) return;
  countedSystems.add(key);
  countEvent(systemChosenEvent(platform), currentLabel);
}

function resetLesson() {
  lookupId += 1;
  current = null;
  linkInput.removeAttribute("aria-invalid");
  setStatus("");
  lessonCard.hidden = true;
  lessonCard.replaceChildren();
  renderCommand();
}

async function checkLink() {
  const id = ++lookupId;
  const text = linkInput.value;
  if (text.trim() === "") {
    resetLesson();
    return;
  }

  const parsed = parseLessonLink(text);
  if (parsed.error) {
    current = null;
    renderCommand();
    showError(parsed.error);
    return;
  }

  current = null;
  renderCommand();
  showLoading();
  const lesson = await fetchLesson(parsed.lessonId);
  if (id !== lookupId) return; // the visitor has typed something else since

  if (lesson.error) {
    current = null;
    renderCommand();
    showError(lesson.error);
    return;
  }
  current = schedule(lesson);
  currentLabel = classLabel(lesson, current);
  countEvent(lessonLookedUpEvent(currentLabel), lesson.facility);
  renderLesson(lesson, current);
  renderCommand();
}

function queueCheck() {
  clearTimeout(checkTimer);
  checkTimer = setTimeout(checkLink, CHECK_DELAY_MS);
}

function fallbackCopy(text) {
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.append(area);
  area.select();
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch {
    copied = false;
  }
  area.remove();
  return copied;
}

async function copyCommand() {
  const text = commandText.textContent;
  let copied = false;
  try {
    await navigator.clipboard.writeText(text);
    copied = true;
  } catch {
    copied = fallbackCopy(text);
  }
  if (!copied) return;

  countEvent(commandCopiedEvent(platform, currentLabel));
  copyButton.textContent = "Copied ✓";
  clearTimeout(copyTimer);
  copyTimer = setTimeout(() => {
    copyButton.textContent = "Copy";
  }, COPIED_MS);
}

function choosePlatform(value) {
  platform = value;
  for (const input of platformInputs) {
    input.checked = input.value === value;
  }
  renderCommand();
}

// Wiring

linkInput.addEventListener("input", queueCheck);
linkInput.addEventListener("paste", queueCheck);
linkInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    clearTimeout(checkTimer);
    checkLink();
  }
});

for (const input of platformInputs) {
  input.addEventListener("change", () => choosePlatform(input.value));
}

copyButton.addEventListener("click", copyCommand);

startAnalytics();

const onPhoneOrTablet = isPhoneOrTablet(navigator);
if (onPhoneOrTablet) {
  countEvent(PHONE_VISIT_EVENT);
  $("device-banner").hidden = false;
  $("device-note").hidden = false;
  const copyPageLink = $("copy-page-link");
  copyPageLink.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href.split("#")[0]);
      copyPageLink.textContent = "Link copied ✓";
    } catch {
      copyPageLink.textContent = window.location.href.split("#")[0];
    }
  });
}

detectedNote.textContent = onPhoneOrTablet
  ? "Detected: phone or tablet. Choose the system of the computer that will run it."
  : `Detected: ${PLATFORM_NAMES[platform]}`;
choosePlatform(platform);
renderCommand();
