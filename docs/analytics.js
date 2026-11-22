// Anonymous usage counts with GoatCounter (https://www.goatcounter.com).
//
// GoatCounter sets no cookies and stores no IP addresses or personal data. This page sends it
// only: page visits, which classes are looked up, which system the command is shown for,
// clicks on Copy, and visits from phones. Never anything about the visitor's login.

// The site code from your GoatCounter account (https://<code>.goatcounter.com).
// Empty means analytics is switched off.
export const GOATCOUNTER_CODE = "danyk20";

const SYSTEM_NAMES = { macos: "macOS", windows: "Windows", linux: "Linux" };
const LOADER_CHECK_MS = 100;
const LOADER_GIVE_UP_MS = 15000;

// Event names. GoatCounter groups events by this name, so it says what happened and to which
// class, e.g. "lesson: Manege: Akrobatik (Wednesday 19:15)". It must not start with "/".

export function classLabel(lesson, info) {
  const name = lesson.title ? `${lesson.sportName}: ${lesson.title}` : lesson.sportName;
  return `${name} (${info.lessonWeekdayName} ${info.lessonTime})`;
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
