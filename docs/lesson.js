// Pure logic for the setup page: no DOM, no storage. Tested by tests-web/lesson.test.mjs.

export const DEFAULT_SITE_URL = "https://danyk20.github.io/ASVZ-enrollment";
export const LESSON_API_URL = "https://schalter.asvz.ch/tn-api/api/Lessons";
export const ZURICH = "Europe/Zurich";
const EARLY_START_MS = 2 * 60 * 1000;

const WEEKDAY_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

// Takes a lesson link, a bare lesson number, or anything else the visitor pasted.
// Returns {lessonId} on success, or {error} with one of: invalid, event, not-a-lesson.
export function parseLessonLink(text) {
  const input = String(text ?? "").trim();
  if (input === "") return { error: "invalid" };
  if (/^\d+$/.test(input)) return { lessonId: Number(input) };

  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(input) ? input : `https://${input}`;
  let url;
  try {
    url = new URL(withScheme);
  } catch {
    return { error: "invalid" };
  }
  const host = url.hostname.toLowerCase();
  if (host !== "asvz.ch" && !host.endsWith(".asvz.ch")) return { error: "invalid" };

  const lesson = /^\/tn\/lessons\/(\d+)\/?$/.exec(url.pathname);
  if (lesson) return { lessonId: Number(lesson[1]) };
  if (/^\/tn\/events\/\d+/.test(url.pathname)) return { error: "event" };
  return { error: "not-a-lesson" };
}

// Reads one lesson from the ASVZ lesson API. fetchImpl can be replaced in tests.
// Returns the lesson, or {error} with one of: not-found, network.
export async function fetchLesson(lessonId, fetchImpl = fetch) {
  let response;
  try {
    response = await fetchImpl(`${LESSON_API_URL}/${lessonId}`);
  } catch {
    return { error: "network" };
  }
  if (response.status === 404) return { error: "not-found" };
  if (!response.ok) return { error: "network" };

  let body;
  try {
    body = await response.json();
  } catch {
    return { error: "network" };
  }
  const data = body?.data ?? body;
  const starts = new Date(data?.starts);
  const enrolmentOpens = new Date(data?.enrollmentFrom);
  if (Number.isNaN(starts.getTime()) || Number.isNaN(enrolmentOpens.getTime())) {
    return { error: "network" };
  }
  return {
    id: lessonId,
    sportName: data.sportName ?? "",
    title: data.title ?? "",
    starts,
    enrolmentOpens,
    facility: data.facilities?.[0]?.name ?? "",
  };
}

// Weekday and clock time of a moment in Zurich, whatever the visitor's own time zone.
export function zurichParts(date) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: ZURICH,
    weekday: "long",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const value = (type) => parts.find((part) => part.type === type)?.value ?? "";
  const weekdayName = value("weekday");
  return {
    weekday: WEEKDAY_NAMES.indexOf(weekdayName),
    weekdayName,
    hour: Number(value("hour")),
    minute: Number(value("minute")),
  };
}

// The computer starts two minutes before enrolment opens. Crosses midnight correctly.
export function startTime(enrolmentOpens) {
  return new Date(enrolmentOpens.getTime() - EARLY_START_MS);
}

function clock(parts) {
  return `${String(parts.hour).padStart(2, "0")}:${String(parts.minute).padStart(2, "0")}`;
}

// Everything the lesson card and the commands need.
export function schedule(lesson) {
  const start = zurichParts(startTime(lesson.enrolmentOpens));
  const lessonParts = zurichParts(lesson.starts);
  const opens = zurichParts(lesson.enrolmentOpens);
  return {
    lessonId: lesson.id,
    weekday: start.weekday,
    weekdayName: start.weekdayName,
    time: clock(start),
    lessonWeekdayName: lessonParts.weekdayName,
    lessonTime: clock(lessonParts),
    opensWeekdayName: opens.weekdayName,
    opensTime: clock(opens),
  };
}

/**
 * True on phones and tablets. The setup needs a computer (macOS, Windows or Linux): phones
 * can't run the setup command or keep a weekly job running. iPads report themselves as
 * "Macintosh", so a Mac with a touch screen counts as a tablet.
 */
export function isPhoneOrTablet(navigatorLike) {
  if (navigatorLike?.userAgentData?.mobile === true) return true;
  const userAgent = String(navigatorLike?.userAgent || "");
  if (/iPhone|iPad|iPod|Android|Mobile/i.test(userAgent)) return true;
  return /Macintosh/i.test(userAgent) && (navigatorLike?.maxTouchPoints ?? 0) > 1;
}

// Takes the browser's navigator (or any object shaped like it).
// Returns "macos", "windows" or "linux". Unknown systems count as macOS.
export function detectPlatform(navigatorLike) {
  const fromData = navigatorLike?.userAgentData?.platform;
  const text = String(fromData || navigatorLike?.platform || navigatorLike?.userAgent || "")
    .toLowerCase();
  if (text.includes("win")) return "windows";
  if (text.includes("android") || text.includes("iphone") || text.includes("ipad")) {
    return "macos";
  }
  if (text.includes("mac")) return "macos";
  if (text.includes("linux") || text.includes("x11") || text.includes("cros")) return "linux";
  return "macos";
}

// The one command for the visitor's system, with the lesson filled in.
export function buildCommand(platform, scheduleInfo, siteUrl = DEFAULT_SITE_URL) {
  const site = siteUrl.replace(/\/+$/, "");
  const id = scheduleInfo.lessonId;
  if (platform === "windows") {
    return (
      "[Net.ServicePointManager]::SecurityProtocol='Tls12'; " +
      `& ([scriptblock]::Create((irm ${site}/setup.ps1))) ` +
      `-LessonId ${id} -Weekday ${scheduleInfo.weekdayName} -Time ${scheduleInfo.time}`
    );
  }
  return (
    `curl -fsSL ${site}/setup.sh | sh -s -- ` +
    `--lesson-id ${id} --weekday ${scheduleInfo.weekday} --time ${scheduleInfo.time}`
  );
}

// Messages for the parse and fetch errors, shown by app.js.
export const ERROR_MESSAGES = {
  invalid:
    "That doesn't look like an ASVZ lesson link. It should look like https://schalter.asvz.ch/tn/lessons/777113.",
  event:
    "This is a one-off event, not a weekly lesson. Automatic weekly enrolment only works for lessons.",
  "not-a-lesson":
    "Open your specific class first (click it in the timetable), then copy that page's address.",
  "not-found": "ASVZ has no lesson with this number. Check the link.",
  network: "Couldn't reach ASVZ. Check your internet connection and try again.",
};
