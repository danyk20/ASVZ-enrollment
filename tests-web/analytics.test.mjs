import assert from "node:assert/strict";
import { test } from "node:test";

import {
  PHONE_VISIT_EVENT,
  classLabel,
  commandCopiedEvent,
  countEvent,
  lessonLookedUpEvent,
  startAnalytics,
  systemChosenEvent,
} from "../docs/analytics.js";

const LESSON = { sportName: "Manege", title: "Akrobatik", facility: "Sport Center Hönggerberg" };
const INFO = { lessonWeekdayName: "Wednesday", lessonTime: "19:15" };

test("event names say what happened and to which class", () => {
  const label = classLabel(LESSON, INFO);
  assert.equal(label, "Manege: Akrobatik (Wednesday 19:15)");
  assert.equal(lessonLookedUpEvent(label), "lesson: Manege: Akrobatik (Wednesday 19:15)");
  assert.equal(systemChosenEvent("windows"), "system: Windows");
  assert.equal(commandCopiedEvent("macos", label), "copy: macOS · Manege: Akrobatik (Wednesday 19:15)");
  assert.equal(PHONE_VISIT_EVENT, "phone-visit");
  assert.equal(classLabel({ sportName: "Squash", title: "" }, INFO), "Squash (Wednesday 19:15)");
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
