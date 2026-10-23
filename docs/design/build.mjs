#!/usr/bin/env node
// Builds the five blueprint figures for the design dossier.
import { writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { figure } from "./_kit.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const FIG_DIR = join(HERE, "figures");
mkdirSync(FIG_DIR, { recursive: true });

const pipeline = figure(
  "fig-pipeline",
  {
    height: 520,
    title: "the plan pipeline",
    desc: "Six stages inside PlanView.post: validate, route with OsrmRouter.plan, sample with sample_along_route, fetch with OpenMeteoWeather.fetch_many, classify with risk.assess, order with ranking_key.",
  },
  (f) => {
    f.kicker(20, 28, "backend · routing/services");
    const rows = [
      ["PlanView.post()", "validates the body, builds PlanInput", "blue", 1],
      ["OsrmRouter.plan()", "alternatives first, then via-point detours", "violet", 2],
      ["sample_along_route()", "carries cumulative miles per point", "violet", 3],
      ["OpenMeteoWeather.fetch_many()", "one request per 20 coordinates", "violet", 4],
      ["risk.assess()", "worst of three, then the load gate", "green", 5],
      ["ranking_key()", "lexicographic: risk before time", "green", 6],
    ];
    const top = 48;
    const boxH = 46;
    const gap = 26;
    rows.forEach(([title, note, hue, n], i) => {
      const y = top + i * (boxH + gap);
      f.step(26, y + boxH / 2, n);
      f.box({ x: 44, y, w: 300, h: boxH, hue, title });
      f.text(366, y + boxH / 2 + 4, note, { size: 11, serif: true, hue: "ink-soft", max: 250 });
      if (i < rows.length - 1) f.arrow([194, y + boxH], [194, y + boxH + gap], { style: "call" });
    });
    f.text(44, 492, "one HTTP round trip: the browser never calls a provider directly.", {
      size: 11,
      serif: true,
      hue: "ink-mute",
    });
  },
);

const eta = figure(
  "fig-eta",
  {
    height: 348,
    title: "from miles to a forecast hour",
    desc: "A 300 mile route with checkpoints every 25 miles, mapped onto a clock from 14:00 to 20:08, then read out as the forecast hour each checkpoint samples: 16:00, 17:00, 19:00 and 20:00.",
  },
  (f) => {
    f.kicker(20, 26, "route · 300 mi, checkpoint every 25 mi");
    f.rect({ x: 60, y: 36, w: 540, h: 12, hue: "violet" });
    for (let i = 0; i <= 12; i += 1) {
      const x = 60 + i * 45;
      f.rule(x, 48, x, 56, { hue: "violet", w: 1.2 });
    }
    [0, 3, 6, 9, 12].forEach((i) => {
      const label = String(i * 25);
      f.text(60 + i * 45, 72, label, { size: 11, anchor: "middle", hue: "ink-mute" });
    });

    f.kicker(20, 100, "clock · the same axis, relabelled in hours");
    f.rect({ x: 60, y: 110, w: 540, h: 12, hue: "amber" });
    f.text(60, 140, "14:00", { size: 12 });
    f.text(330, 140, "17:04", { size: 12, anchor: "middle" });
    f.text(600, 140, "20:08", { size: 12, anchor: "end" });

    f.kicker(20, 172, "what each checkpoint reads");
    f.rule(20, 180, 620, 180);
    const cols = [20, 110, 250, 330, 430, 530];
    ["mile", "eta", "reads", "wind", "rain", "level"].forEach((h, i) => {
      f.kicker(cols[i], 196, h);
    });
    f.rule(20, 204, 620, 204);
    const rows = [
      ["75", "15:32", "16:00", "26.7 mph", "0.00 in/hr", "Moderate", "olive"],
      ["150", "17:04", "17:00", "15.9 mph", "0.00 in/hr", "Low", "green"],
      ["225", "18:36", "19:00", "20.4 mph", "0.78 in/hr", "Severe", "rose"],
      ["300", "20:08", "20:00", "18.5 mph", "0.00 in/hr", "Low", "green"],
    ];
    rows.forEach(([mile, time, hour, wind, rain, level, hue], i) => {
      const y = 224 + i * 26;
      f.text(cols[0], y, mile, { size: 12 });
      f.text(cols[1], y, time, { size: 12 });
      f.text(cols[2], y, hour, { size: 12, hue: "ink-soft" });
      f.text(cols[3], y, wind, { size: 12 });
      f.text(cols[4], y, rain, { size: 12 });
      f.text(cols[5], y, level, { size: 12, hue });
      if (i < rows.length - 1) f.rule(20, y + 9, 620, y + 9);
    });
    f.rule(20, 316, 620, 316);
    f.text(20, 336, "eta = departure + duration × (miles / total miles)", { size: 11.5, serif: true, hue: "ink-soft" });
  },
);

const record = figure(
  "fig-record",
  {
    height: 312,
    title: "the checkpoint record",
    desc: "Eight fields each checkpoint carries from Django to the map: miles, eta, wind_mph, rain_in_hr, snow_in_hr, level, driver and reasons.",
  },
  (f) => {
    f.kicker(20, 22, "the record");
    f.kicker(330, 22, "what each field is for");
    f.rect({ x: 20, y: 32, w: 300, h: 28, hue: "teal" });
    f.text(32, 51, "checkpoint", { size: 12.5, weight: 700 });
    const fields = [
      ["miles", "0 .. 299.4", "distance from the origin"],
      ["eta", "2026-10-24T15:27Z", "the instant the truck is there"],
      ["wind_mph", "9.0", "forecast wind at that hour"],
      ["rain_in_hr", "0.00", "forecast rain rate"],
      ["snow_in_hr", "0.00", "forecast snowfall rate"],
      ["level", "0", "0 Low .. 4 No Travel"],
      ["driver", "wind", "which condition decided it"],
      ["reasons", "wind 9 mph", "the rule that fired, in words"],
    ];
    fields.forEach(([name, value, note], i) => {
      const y = 60 + i * 28;
      f.rect({ x: 20, y, w: 300, h: 28, hue: "paper" });
      f.text(32, y + 18, name, { size: 12, hue: "ink-soft" });
      f.text(150, y + 18, value, { size: 12 });
      f.rule(306, y + 14, 324, y + 14, { hue: "teal" });
      f.text(330, y + 18, note, { size: 11, serif: true, hue: "ink-soft" });
    });
  },
);

const decision = figure(
  "fig-decision",
  {
    height: 404,
    title: "three conditions, one level",
    desc: "Wind, rain and snow are classified separately, the worst wins, then the load escalation rules run and can only raise the level, ending at one of five levels.",
  },
  (f) => {
    f.kicker(20, 26, "one checkpoint");
    f.box({ x: 20, y: 40, w: 180, h: 44, hue: "violet", title: "wind_mph", sub: "classify_wind()" });
    f.box({ x: 230, y: 40, w: 180, h: 44, hue: "violet", title: "rain_in_hr", sub: "classify_rain()" });
    f.box({ x: 440, y: 40, w: 180, h: 44, hue: "violet", title: "snow_in_hr", sub: "classify_snow()" });

    f.arrow([110, 84], [150, 124], { style: "call" });
    f.arrow([320, 84], [320, 124], { style: "call" });
    f.arrow([530, 84], [490, 124], { style: "call" });
    f.box({ x: 150, y: 124, w: 340, h: 44, hue: "grey", title: "max of the three", sub: "the worst condition wins" });

    f.arrow([320, 168], [320, 202], { style: "model" });
    f.text(334, 190, "then", { size: 11, serif: true, hue: "ink-mute" });

    f.rect({ x: 20, y: 202, w: 580, h: 92, hue: "green" });
    f.kicker(32, 220, "load escalation");
    f.text(32, 242, "wind ≥ 55 mph → No Travel, any load", { size: 11.5 });
    f.text(32, 264, "wind 45-54 mph and load > 30,000 lb → No Travel", { size: 11.5 });
    f.text(32, 286, "wind 35-44 mph and load > 40,000 lb → Severe", { size: 11.5 });

    f.arrow([320, 294], [320, 326], { style: "state" });
    const chips = [
      ["Low", "green", false],
      ["Moderate", "olive", false],
      ["High", "indigo", false],
      ["Severe", "rose", false],
      ["No Travel", "rose", true],
    ];
    chips.forEach(([label, hue, double], i) => {
      const x = 20 + i * 118;
      f.rect({ x, y: 326, w: 108, h: 40, hue, double });
      f.text(x + 54, 351, label, { size: 12.5, weight: 700, anchor: "middle", max: 84 });
    });
    f.text(20, 392, "double border: a terminal level · escalation only raises, never lowers", {
      size: 11,
      serif: true,
      hue: "ink-mute",
    });
  },
);

const ranking = figure(
  "fig-rank",
  {
    height: 374,
    title: "why the fastest route loses",
    desc: "Two routes compared on the four ranking keys. They tie on severe miles, so the second key, high miles, decides, and the slower route is recommended.",
  },
  (f) => {
    f.kicker(20, 26, "A · fastest");
    f.kicker(336, 26, "B · alternate a");
    f.rule(320, 34, 320, 348, { dash: "dashed" });
    const rows = [
      ["severe miles", "75.0 mi", "75.0 mi"],
      ["high miles", "25.0 mi", "0.0 mi"],
      ["avg risk", "1.17", "0.91"],
      ["drive time", "6 h 08 m", "8 h 28 m"],
      ["rank", "#3 of 3", "#1 of 3"],
    ];
    rows.forEach(([label, a, b], i) => {
      const y = 40 + i * 62;
      f.rect({ x: 20, y, w: 284, h: 44, hue: "paper" });
      f.text(32, y + 17, label, { size: 11, hue: "ink-mute" });
      f.text(32, y + 36, a, { size: 13, weight: 700 });
      f.rect({ x: 336, y, w: 284, h: 44, hue: "paper" });
      f.text(348, y + 17, label, { size: 11, hue: "ink-mute" });
      f.text(348, y + 36, b, { size: 13, weight: 700 });
    });
    f.text(20, 362, "ranking_key = (no_travel, severe, high, avg_risk, duration)", { size: 11, hue: "ink-soft" });
  },
);

const all = { "fig-1": pipeline, "fig-2": eta, "fig-3": record, "fig-4": decision, "fig-5": ranking };
Object.entries(all).forEach(([name, svg]) => {
  writeFileSync(join(FIG_DIR, name + ".svg"), svg);
  console.log("wrote figures/" + name + ".svg", Buffer.byteLength(svg) + " bytes");
});
