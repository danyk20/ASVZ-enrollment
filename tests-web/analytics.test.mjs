import assert from "node:assert/strict";
import { test } from "node:test";

import {
  FUNNEL,
  PHONE_VISIT_EVENT,
  classLabel,
  commandCopiedEvent,
  countEvent,
  countOnce,
  linkClickEvent,
  lessonLookedUpEvent,
  lookupFailedEvent,
  startAnalytics,
  systemChosenEvent,
  visitTimeEvents,
} from "../docs/analytics.js";

const LESSON = { sportName: "Manege", title: "Akrobatik", facility: "Sport Center Hönggerberg" };
const INFO = { lessonId: 777113, lessonWeekdayName: "Wednesday", lessonTime: "19:15" };

test("event names say what happened and to which class", () => {
  const label = classLabel(LESSON, INFO);
  assert.equal(label, "Manege: Akrobatik (Wednesday 19:15) #777113");
  assert.equal(lessonLookedUpEvent(label), "lesson: Manege: Akrobatik (Wednesday 19:15) #777113");
  assert.equal(systemChosenEvent("windows"), "system: Windows");
  assert.equal(commandCopiedEvent("macos", label), "copy: macOS · Manege: Akrobatik (Wednesday 19:15) #777113");
  assert.equal(PHONE_VISIT_EVENT, "phone-visit");
  assert.equal(classLabel({ sportName: "Squash", title: "" }, INFO), "Squash (Wednesday 19:15) #777113");
});

test("no event name starts with a slash, which GoatCounter rejects", () => {
  const label = classLabel(LESSON, INFO);
  for (const name of [lessonLookedUpEvent(label), systemChosenEvent("linux"),
                      commandCopiedEvent("linux", label), PHONE_VISIT_EVENT]) {
    assert.notEqual(name[0], "/");
  }
});

test("events wait for GoatCounter's script, then are sent; nothing is sent while off", async () => {
  const sent = [];
  const added = [];
  globalThis.window = {};
  globalThis.document = {
    createElement: () => ({ dataset: {} }),
    head: { append: (element) => added.push(element) },
  };

  countEvent("before-start");               // analytics not started: ignored
  startAnalytics("");                       // no code: stays off
  countEvent("still-off");
  assert.equal(added.length, 0);

  startAnalytics("my-site");
  assert.equal(added[0].src, "https://gc.zgo.at/count.js");
  assert.equal(added[0].dataset.goatcounter, "https://my-site.goatcounter.com/count");

  countEvent("lesson: X", "Hall 1");        // script not loaded yet: queued
  window.goatcounter = { count: (event) => sent.push(event) };
  await new Promise((resolve) => setTimeout(resolve, 250));
  countEvent("copy: macOS · X");            // script loaded: sent at once

  assert.deepEqual(sent, [
    { path: "lesson: X", title: "Hall 1", event: true },
    { path: "copy: macOS · X", title: "copy: macOS · X", event: true },
  ]);
});

test("failed lookups send only the reason", () => {
  assert.equal(lookupFailedEvent("invalid"), "lookup failed: not a lesson link");
  assert.equal(lookupFailedEvent("event"), "lookup failed: one-off event, not a lesson");
  assert.equal(lookupFailedEvent("not-a-lesson"), "lookup failed: sport or timetable page, not a class");
  assert.equal(lookupFailedEvent("not-found"), "lookup failed: lesson number not found");
  assert.equal(lookupFailedEvent("network"), "lookup failed: ASVZ could not be reached");
});

test("link clicks and funnel steps have readable, sortable names", () => {
  assert.equal(linkClickEvent("View on GitHub · hero"), "click: View on GitHub · hero");
  assert.deepEqual(Object.values(FUNNEL), [
    "funnel 1 · page visit",
    "funnel 2 · link entered",
    "funnel 3 · lesson found",
    "funnel 4 · command copied",
  ]);
});

test("visit time is the weekday and hour in Swiss time, whatever the visitor's time zone", () => {
  // 18:05 UTC on Tuesday 24 November 2026 is 19:05 in Zurich (winter time)
  assert.deepEqual(visitTimeEvents(new Date("2026-11-24T18:05:00Z")),
    ["visit day: Tuesday", "visit hour: 19:00–19:59"]);
  // 22:30 UTC on Saturday 1 August 2026 is 00:30 on Sunday in Zurich (summer time)
  assert.deepEqual(visitTimeEvents(new Date("2026-08-01T22:30:00Z")),
    ["visit day: Sunday", "visit hour: 00:00–00:59"]);
});

test("countOnce sends an event only the first time in a page visit", async () => {
  const sent = [];
  window.goatcounter = { count: (event) => sent.push(event.path) };
  countOnce("funnel 2 · link entered");
  countOnce("funnel 2 · link entered");
  countOnce("funnel 3 · lesson found");
  assert.deepEqual(sent, ["funnel 2 · link entered", "funnel 3 · lesson found"]);
});
