/**
 * Formatting is on every page: money, percentages and dates must be consistent.
 * Run with `npm test` (Node's built-in test runner; Node ≥ 23 strips TypeScript types natively).
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { bytes, day, nok, nokCompact, num, pct, rel } from "./format.ts";

test("nok: Norwegian grouping, no decimals by default, dash for missing", () => {
  assert.equal(nok(1234), "1 234 NOK");
  assert.equal(nok(-980.4), "-980 NOK");
  assert.equal(nok(0), "0 NOK");
  assert.equal(nok(null), "—");
  assert.equal(nok(undefined), "—");
  assert.equal(nok(Number.NaN), "—");
});

test("nokCompact: exact below 10k, compact above", () => {
  assert.equal(nokCompact(9999), "9 999 NOK");
  assert.match(nokCompact(12_345), /^12,3k NOK$/);
  assert.equal(nokCompact(null), "—");
});

test("pct: ratios in, percent out, optional sign", () => {
  assert.equal(pct(0.1234), "12.3%");
  assert.equal(pct(0.05, 1, true), "+5.0%");
  assert.equal(pct(-0.05, 1, true), "-5.0%");
  assert.equal(pct(null), "—");
});

test("num: fixed digits, dash for missing", () => {
  assert.equal(num(95.46, 1), "95.5");
  assert.equal(num(undefined), "—");
});

test("day: plain dates are not shifted by time zones", () => {
  assert.match(day("2026-09-30"), /30/);
  assert.equal(day(null), "—");
});

test("rel: naive API timestamps are UTC", () => {
  const minsAgo = new Date(Date.now() - 5 * 60_000).toISOString().replace("Z", "");
  assert.equal(rel(minsAgo), "5 min ago");
  const inHour = new Date(Date.now() + 61 * 60_000).toISOString().replace("Z", "");
  assert.equal(rel(inHour), "in 1 h");
  assert.equal(rel(null), "—");
});

test("bytes", () => {
  assert.equal(bytes(512), "512 B");
  assert.equal(bytes(1536), "1.5 KB");
  assert.equal(bytes(null), "—");
});
