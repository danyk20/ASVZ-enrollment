// Tests for docs/lesson.js. Run with: node --test tests-web/
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildCommand,
  detectPlatform,
  isPhoneOrTablet,
  fetchLesson,
  parseLessonLink,
  schedule,
  startTime,
  zurichParts,
} from "../docs/lesson.js";

const SITE = "https://danyk20.github.io/ASVZ-enrollment";

test("parseLessonLink accepts a full lesson link", () => {
  assert.deepEqual(parseLessonLink("https://schalter.asvz.ch/tn/lessons/777113"), {
    lessonId: 777113,
  });
});

test("parseLessonLink accepts a link without https, with a trailing slash, query or hash", () => {
  assert.deepEqual(parseLessonLink("schalter.asvz.ch/tn/lessons/777113"), { lessonId: 777113 });
  assert.deepEqual(parseLessonLink("https://schalter.asvz.ch/tn/lessons/777113/"), {
    lessonId: 777113,
  });
  assert.deepEqual(parseLessonLink("https://schalter.asvz.ch/tn/lessons/777113?x=1#top"), {
    lessonId: 777113,
  });
});

test("parseLessonLink accepts a bare lesson number and trims spaces", () => {
  assert.deepEqual(parseLessonLink("  777113 \n"), { lessonId: 777113 });
});

test("parseLessonLink reports one-off events", () => {
  assert.deepEqual(parseLessonLink("https://schalter.asvz.ch/tn/events/4242"), { error: "event" });
});

test("parseLessonLink reports asvz.ch pages that are not lessons", () => {
  assert.deepEqual(parseLessonLink("https://www.asvz.ch/426-sportfahrplan"), {
    error: "not-a-lesson",
  });
  assert.deepEqual(parseLessonLink("https://schalter.asvz.ch/tn/"), { error: "not-a-lesson" });
});

test("parseLessonLink rejects empty text, garbage and other websites", () => {
  assert.deepEqual(parseLessonLink(""), { error: "invalid" });
  assert.deepEqual(parseLessonLink("   "), { error: "invalid" });
  assert.deepEqual(parseLessonLink("karate"), { error: "invalid" });
  assert.deepEqual(parseLessonLink("https://example.org/tn/lessons/777113"), { error: "invalid" });
  assert.deepEqual(parseLessonLink("https://notasvz.ch/tn/lessons/777113"), { error: "invalid" });
});

test("zurichParts gives Zurich time in winter (CET, UTC+1)", () => {
  // 2 December 2026, 18:15 UTC is 19:15 in Zurich.
  const parts = zurichParts(new Date("2026-12-02T18:15:00Z"));
  assert.equal(parts.weekdayName, "Wednesday");
  assert.equal(parts.weekday, 3);
  assert.equal(parts.hour, 19);
  assert.equal(parts.minute, 15);
});

test("zurichParts gives Zurich time in summer (CEST, UTC+2)", () => {
  // 7 July 2026, 17:15 UTC is 19:15 in Zurich.
  const parts = zurichParts(new Date("2026-07-07T17:15:00Z"));
  assert.equal(parts.weekdayName, "Tuesday");
  assert.equal(parts.weekday, 2);
  assert.equal(parts.hour, 19);
  assert.equal(parts.minute, 15);
});

test("startTime is two minutes before enrolment opens", () => {
  const opens = new Date("2026-12-01T18:15:00Z");
  assert.equal(startTime(opens).toISOString(), "2026-12-01T18:13:00.000Z");
});

test("startTime crosses midnight: opening Monday 00:01 starts Sunday 23:59", () => {
  // Monday 7 December 2026, 00:01 in Zurich (CET) is Sunday 6 December 23:01 UTC.
  const opens = new Date("2026-12-06T23:01:00Z");
  const start = zurichParts(startTime(opens));
  assert.equal(start.weekdayName, "Sunday");
  assert.equal(start.weekday, 0);
  assert.equal(start.hour, 23);
  assert.equal(start.minute, 59);
});

test("schedule describes the lesson, the opening and the computer start", () => {
  const info = schedule({
    id: 777113,
    sportName: "Manege",
    title: "Akrobatik",
    starts: new Date("2026-12-02T18:15:00Z"), // Wednesday 19:15 Zurich
    enrolmentOpens: new Date("2026-12-01T18:15:00Z"), // Tuesday 19:15 Zurich
  });
  assert.deepEqual(info, {
    lessonId: 777113,
    weekday: 2,
    weekdayName: "Tuesday",
    time: "19:13",
    lessonWeekdayName: "Wednesday",
    lessonTime: "19:15",
    opensWeekdayName: "Tuesday",
    opensTime: "19:15",
  });
});

test("buildCommand makes the macOS and Linux command", () => {
  const info = { lessonId: 777113, weekday: 2, weekdayName: "Tuesday", time: "19:13" };
  assert.equal(
    buildCommand("macos", info, SITE),
    `curl -fsSL ${SITE}/setup.sh | sh -s -- --lesson-id 777113 --weekday 2 --time 19:13`,
  );
  assert.equal(buildCommand("linux", info, SITE), buildCommand("macos", info, SITE));
});

test("buildCommand makes the Windows command with the day name", () => {
  const info = { lessonId: 777113, weekday: 2, weekdayName: "Tuesday", time: "19:13" };
  assert.equal(
    buildCommand("windows", info, SITE),
    "[Net.ServicePointManager]::SecurityProtocol='Tls12'; " +
      `& ([scriptblock]::Create((irm ${SITE}/setup.ps1))) ` +
      "-LessonId 777113 -Weekday Tuesday -Time 19:13",
  );
});

test("buildCommand uses the default site address and ignores a trailing slash", () => {
  const info = { lessonId: 1, weekday: 2, weekdayName: "Tuesday", time: "19:13" };
  assert.match(buildCommand("macos", info), /^curl -fsSL https:\/\/danyk20\.github\.io\/ASVZ-enrollment\/setup\.sh \| sh/);
  assert.equal(buildCommand("macos", info, `${SITE}/`), buildCommand("macos", info, SITE));
});

test("detectPlatform prefers userAgentData, then platform, then userAgent", () => {
  assert.equal(detectPlatform({ userAgentData: { platform: "Windows" } }), "windows");
  assert.equal(detectPlatform({ userAgentData: { platform: "macOS" } }), "macos");
  assert.equal(detectPlatform({ userAgentData: { platform: "Linux" } }), "linux");
  assert.equal(detectPlatform({ platform: "Win32" }), "windows");
  assert.equal(detectPlatform({ platform: "MacIntel" }), "macos");
  assert.equal(
    detectPlatform({ userAgent: "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101" }),
    "linux",
  );
});

test("detectPlatform falls back to macOS when unknown", () => {
  assert.equal(detectPlatform({}), "macos");
  assert.equal(detectPlatform(undefined), "macos");
  assert.equal(detectPlatform({ platform: "Plan9" }), "macos");
});

function fakeFetch(response) {
  return async () => response;
}

const LESSON_BODY = {
  data: {
    id: 777113,
    sportName: "Manege",
    title: "Akrobatik",
    starts: "2026-12-02T19:15:00+01:00",
    enrollmentFrom: "2026-11-30T19:15:00+01:00",
    facilities: [{ name: "Sport Center Hönggerberg" }],
  },
};

test("fetchLesson returns the lesson from a 200 answer", async () => {
  const lesson = await fetchLesson(777113, fakeFetch({
    ok: true,
    status: 200,
    json: async () => LESSON_BODY,
  }));
  assert.equal(lesson.id, 777113);
  assert.equal(lesson.sportName, "Manege");
  assert.equal(lesson.title, "Akrobatik");
  assert.equal(lesson.facility, "Sport Center Hönggerberg");
  assert.equal(lesson.starts.toISOString(), "2026-12-02T18:15:00.000Z");
  assert.equal(lesson.enrolmentOpens.toISOString(), "2026-11-30T18:15:00.000Z");
});

test("fetchLesson reports not-found for a 404 answer", async () => {
  const result = await fetchLesson(1, fakeFetch({ ok: false, status: 404 }));
  assert.deepEqual(result, { error: "not-found" });
});

test("fetchLesson reports network for a failed request", async () => {
  const result = await fetchLesson(1, async () => {
    throw new TypeError("Failed to fetch");
  });
  assert.deepEqual(result, { error: "network" });
});

test("fetchLesson reports network for a server error", async () => {
  const result = await fetchLesson(1, fakeFetch({ ok: false, status: 500 }));
  assert.deepEqual(result, { error: "network" });
});

test("isPhoneOrTablet recognises phones and tablets, not computers", () => {
  const iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148";
  const android = "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36";
  const ipadAsMac = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15";
  assert.equal(isPhoneOrTablet({ userAgent: iphone }), true);
  assert.equal(isPhoneOrTablet({ userAgent: android }), true);
  assert.equal(isPhoneOrTablet({ userAgent: ipadAsMac, maxTouchPoints: 5 }), true);
  assert.equal(isPhoneOrTablet({ userAgentData: { mobile: true, platform: "Android" } }), true);

  assert.equal(isPhoneOrTablet({ userAgent: ipadAsMac, maxTouchPoints: 0 }), false); // a Mac
  assert.equal(isPhoneOrTablet({ userAgentData: { mobile: false, platform: "Windows" } }), false);
  assert.equal(
    isPhoneOrTablet({ userAgent: "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/133.0" }),
    false,
  );
});
