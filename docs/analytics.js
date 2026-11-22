// Anonymous usage counts with GoatCounter (https://www.goatcounter.com).
//
// GoatCounter sets no cookies and stores no IP addresses or personal data. This page sends it
// only: page visits, which classes are looked up, which system the command is shown for,
// clicks on Copy and on the GitHub links, why a lookup failed, the steps of the setup funnel,
// the weekday and hour of the visit, and visits from phones. Never anything about the
// visitor's login, and never the text they typed.

// The site code from your GoatCounter account (https://<code>.goatcounter.com).
// Empty means analytics is switched off.
export const GOATCOUNTER_CODE = "danyk20";

const SYSTEM_NAMES = { macos: "macOS", windows: "Windows", linux: "Linux" };
const LOADER_CHECK_MS = 100;
const LOADER_GIVE_UP_MS = 15000;

// Event names. GoatCounter groups events by this name, so it says what happened and to which
// class, e.g. "lesson: Manege: Akrobatik (Wednesday 19:15) #777113". It must not start with "/".

export function classLabel(lesson, info) {
  const name = lesson.title ? `${lesson.sportName}: ${lesson.title}` : lesson.sportName;
  return `${name} (${info.lessonWeekdayName} ${info.lessonTime}) #${info.lessonId}`;
}

export function lessonLookedUpEvent(label) {
  return `lesson: ${label}`;
}

export function systemChosenEvent(platform) {
  return `system: ${SYSTEM_NAMES[platform] ?? platform}`;
}

export function commandCopiedEvent(platform, label) {
  return `copy: ${SYSTEM_NAMES[platform] ?? platform} · ${label}`;
}

export const PHONE_VISIT_EVENT = "phone-visit";

// Why a pasted link could not be used. Only the reason is sent, never what was typed.
const FAILURE_REASONS = {
  invalid: "not a lesson link",
  event: "one-off event, not a lesson",
  "not-a-lesson": "sport or timetable page, not a class",
  "not-found": "lesson number not found",
  network: "ASVZ could not be reached",
};

export function lookupFailedEvent(errorCode) {
  return `lookup failed: ${FAILURE_REASONS[errorCode] ?? errorCode}`;
}

export function linkClickEvent(name) {
  return `click: ${name}`;
}

// The setup funnel. Each step is counted at most once per page visit, so comparing the four
// counts shows how many visitors get how far. The numbers keep them sorted together.
export const FUNNEL = {
  visit: "funnel 1 · page visit",
  linkEntered: "funnel 2 · link entered",
  lessonFound: "funnel 3 · lesson found",
  commandCopied: "funnel 4 · command copied",
};

/** When the page was used, in Swiss time: one event for the weekday, one for the hour. */
export function visitTimeEvents(date) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/Zurich",
      weekday: "long",
      hour: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(date)
      .map((part) => [part.type, part.value]),
  );
  const hour = parts.hour.padStart(2, "0");
  return [`visit day: ${parts.weekday}`, `visit hour: ${hour}:00–${hour}:59`];
}

// Sending

const waiting = [];
let started = false;

/** Loads GoatCounter's script, which also counts the page visit. */
export function startAnalytics(code = GOATCOUNTER_CODE) {
  if (!code || started) return;
  started = true;

  const script = document.createElement("script");
  script.async = true;
  script.src = "https://gc.zgo.at/count.js";
  script.dataset.goatcounter = `https://${code}.goatcounter.com/count`;
  document.head.append(script);

  // count.js loads asynchronously; send the events that happened before it was ready.
  const startedAt = Date.now();
  const timer = setInterval(() => {
    if (window.goatcounter?.count) {
      clearInterval(timer);
      waiting.splice(0).forEach(send);
    } else if (Date.now() - startedAt > LOADER_GIVE_UP_MS) {
      clearInterval(timer); // blocked by an ad blocker or offline: drop the events quietly
      waiting.length = 0;
    }
  }, LOADER_CHECK_MS);
}

const countedOnce = new Set();

/** Counts an event only the first time it happens during this page visit. */
export function countOnce(name, title = "") {
  if (countedOnce.has(name)) return;
  countedOnce.add(name);
  countEvent(name, title);
}

/** Counts one event. Does nothing while analytics is switched off. */
export function countEvent(name, title = "") {
  if (!started) return;
  const event = { path: name, title: title || name, event: true };
  if (window.goatcounter?.count) {
    send(event);
  } else {
    waiting.push(event);
  }
}

function send(event) {
  try {
    window.goatcounter.count(event);
  } catch {
    // Analytics must never break the setup tool.
  }
}
