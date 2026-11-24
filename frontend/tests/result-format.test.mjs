import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { resultRows, tennisSets, tennisSetLabel, tennisStatusLabel, resultSummary, weightliftingMedalists, weightliftingClass, weightliftingTotal, attemptLabel } = await loadModule("result-format");
const provenance = { source_url: "https://example.com/official-result", checked_date: "2026-11-04" };
const final = (fields = {}) => ({ kind: "tennis-final", winner: { name: "Match winner", participant_id: "w" },
  runner_up: { name: "Runner-up", participant_id: "r" }, status: "final", ...provenance, ...fields });

test("podium ranks retain source ordering and tied places rather than being renumbered or sorted", () => {
  const result = { kind: "podium", rows: [
    { rank: 3, name: "Source first", participant_id: "c" },
    { rank: 1, name: "Tied first Z", participant_id: "z" },
    { rank: 1, name: "Tied first A", participant_id: "a" },
  ], ...provenance };
  const before = structuredClone(result);
  assert.deepEqual(resultRows(result), [
    { label: "3", name: "Source first", participant_id: "c" },
    { label: "1", name: "Tied first Z", participant_id: "z" },
    { label: "1", name: "Tied first A", participant_id: "a" },
  ]);
  assert.deepEqual(result, before);
});

test("relay awards keep repeated literal country labels and null/missing IDs without fabricating squad identities", () => {
  const result = { kind: "podium", rows: [
    { rank: 1, name: "CHN", participant_id: null },
    { rank: 2, name: "CHN", participant_id: null },
  ], ...provenance };
  const before = structuredClone(result);
  assert.deepEqual(resultRows(result), [
    { label: "1", name: "CHN", participant_id: null },
    { label: "2", name: "CHN", participant_id: null },
  ]);
  assert.deepEqual(result, before);
  assert.deepEqual(resultRows({ ...result, rows: [{ rank: 1, name: "CHN" }] }),
    [{ label: "1", name: "CHN", participant_id: undefined }]);
});

test("a tied podium retains every supplied finisher without an arbitrary row limit", () => {
  const rows = Array.from({ length: 18 }, (_, i) => ({ rank: i < 2 ? i + 1 : 3, name: `Finisher ${i}`, participant_id: `${i}` }));
  const formatted = resultRows({ kind: "podium", rows, ...provenance });
  assert.equal(formatted.length, 18);
  assert.deepEqual(formatted.map(row => row.label), rows.map(row => String(row.rank)));
  assert.deepEqual(formatted.map(row => row.participant_id), rows.map(row => row.participant_id));
});

test("tennis set pairs stay in match-winner orientation even when the champion lost the first set", () => {
  const result = final({ score: { winner: [{ value: 3, winner: false }, { value: 7, tiebreak: 7, winner: true }, { value: 6, winner: true }],
    runner_up: [{ value: 6, winner: true }, { value: 6, tiebreak: 5, winner: false }, { value: 0, winner: false }] } });
  const before = structuredClone(result);
  assert.deepEqual(resultRows(result), [
    { label: "Champion", name: "Match winner", participant_id: "w" },
    { label: "Runner-up", name: "Runner-up", participant_id: "r" },
  ]);
  assert.deepEqual(tennisSets(result), [
    { winner: { value: 3, winner: false }, runner_up: { value: 6, winner: true } },
    { winner: { value: 7, tiebreak: 7, winner: true }, runner_up: { value: 6, tiebreak: 5, winner: false } },
    { winner: { value: 6, winner: true }, runner_up: { value: 0, winner: false } },
  ]);
  assert.deepEqual(result, before);
});

test("tie-break points and zero values survive, with no guessed set-winner marker", () => {
  assert.equal(tennisSetLabel({ value: 6, tiebreak: 0, winner: false }), "6 (tie-break 0)");
  assert.equal(tennisSetLabel({ value: 7, tiebreak: 7, winner: true }), "7 (tie-break 7), set winner");
  assert.equal(tennisSetLabel({ value: 0 }), "0");
  assert.equal(tennisSetLabel({ value: 6 }), "6");
});

test("a confirmed champion without a supplied score has identities and no invented score columns", () => {
  const result = final();
  assert.deepEqual(tennisSets(result), []);
  assert.deepEqual(resultRows(result).map(row => row.label), ["Champion", "Runner-up"]);
  assert.equal(tennisStatusLabel(result.status), "Final");
  assert.deepEqual(Object.keys(resultRows(result)[0]).sort(), ["label", "name", "participant_id"]);
});

test("retired finals keep the supplied incomplete set and do not turn its larger value into a set win", () => {
  const result = final({ status: "retired", score: { winner: [{ value: 6, winner: true }, { value: 2 }], runner_up: [{ value: 4, winner: false }, { value: 0 }] } });
  assert.equal(tennisStatusLabel(result.status), "Retired");
  assert.deepEqual(tennisSets(result).at(-1), { winner: { value: 2 }, runner_up: { value: 0 } });
  assert.equal(tennisSetLabel(tennisSets(result).at(-1).winner), "2");
  assert.deepEqual(tennisSets(final({ status: "retired" })), []);
});

test("walkover finals retain the source status and players without fabricating a played set", () => {
  const result = final({ status: "walkover" });
  assert.equal(tennisStatusLabel(result.status), "Walkover");
  assert.deepEqual(tennisSets(result), []);
  assert.deepEqual(resultRows(result).map(row => row.participant_id), ["w", "r"]);
});

const attempts = () => [{ weight_kg: 100, status: "missed" }, { weight_kg: 100, status: "made" }, { weight_kg: null, status: "unused" }];
const lifter = (lot, fields = {}) => ({ lot, name: `Source athlete ${lot}`, nation: "AIN", gender: "women", weight_class: "59", group: "A", guest: false,
  total_rank: null, total_kg: null, snatch: attempts(), clean_and_jerk: attempts(), ...fields });

test("grouped podium summary keeps source category order, labels, tied ranks and repeated literal teams", () => {
  const grouped = { kind: "podiums", categories: [
    { label: "LEAD Women B3", rows: [{ rank: 1, name: "Winner Z", participant_id: "z" }, { rank: 3, name: "Tied third", participant_id: "t" }] },
    { label: "SPEED RELAY Men", rows: [{ rank: 1, name: "CHN" }, { rank: 2, name: "CHN" }] },
  ], ...provenance };
  const before = structuredClone(grouped);
  assert.equal(resultSummary(grouped), "LEAD Women B3: 1 Winner Z · 3 Tied third · SPEED RELAY Men: 1 CHN · 2 CHN");
  assert.deepEqual(grouped, before);
});

test("weightlifting medals use explicit global-class entries without inventing athlete identifiers or local group ranks", () => {
  const bronze = { name: "Official bronze from B", nation: "AIN", gender: "women", weight_class: "59", rank: 3, weight_kg: 210 };
  const gold = { ...bronze, name: "Source gold", rank: 1, weight_kg: 250 };
  const other = { ...gold, name: "Other class gold", gender: "men", weight_class: "+109", weight_kg: 400 };
  const result = { kind: "weightlifting", athletes: Array.from({ length: 19 }, (_, i) => {
    const { lot, ...athlete } = lifter(`unranked-${i}`); return athlete;
  }), total_medalists: [gold, bronze, other], snatch_medalists: [], clean_and_jerk_medalists: [], ...provenance,
  medal_classes: [{ gender: "women", weight_class: "59" }, { gender: "men", weight_class: "+109" }], mixed_classes: true };
  const before = structuredClone(result);
  assert.deepEqual(weightliftingMedalists(result), [gold, bronze, other]);
  assert.equal(result.athletes.length, 19);
  assert.ok(result.athletes.every(athlete => !("lot" in athlete)));
  assert.equal(resultSummary(result), "Women's 59 kg: 1 Source gold · Women's 59 kg: 3 Official bronze from B · Men's +109 kg: 1 Other class gold");
  assert.deepEqual(result, before);
  assert.equal(resultSummary({ ...result, total_medalists: [] }), "");
  const lower = { ...result, medal_classes: [] };
  assert.deepEqual(weightliftingMedalists(lower), []);
  assert.equal(resultSummary(lower), "");
  const mixed = { ...result, medal_classes: [{ gender: "women", weight_class: "59" }] };
  assert.deepEqual(weightliftingMedalists(mixed), [gold, bronze]);
  assert.equal(resultSummary(mixed), "Women's 59 kg: 1 Source gold · Women's 59 kg: 3 Official bronze from B");
  assert.deepEqual(result, before);
});

test("class labels retain combined-class gender, weight and explicit group without inventing a group", () => {
  assert.equal(weightliftingClass(lifter("a", { group: "B" })), "Women's 59 kg · Group B");
  assert.equal(weightliftingClass(lifter("b", { gender: "men", weight_class: "+109", group: null })), "Men's +109 kg");
  assert.equal(weightliftingClass(lifter("c", { weight_class: "64", group: "" })), "Women's 64 kg");
});

test("repeated attempt weights retain separate made/missed facts and unused attempts never acquire zero", () => {
  const rows = attempts();
  assert.deepEqual(rows.map(attemptLabel), ["100 kg, missed", "100 kg, made", "Unused"]);
  assert.equal(weightliftingTotal(lifter("dns")), "");
  assert.equal(weightliftingTotal(lifter("explicit-zero", { total_kg: 0 })), "0 kg");
  assert.equal(weightliftingTotal(lifter("finished", { total_kg: 210 })), "210 kg");
  assert.equal(lifter("dns").total_rank, null);
});

test("tennis summaries preserve winner-oriented paired scores, both tie-break values and final statuses", () => {
  const result = final({ score: { winner: [{ value: 6, tiebreak: 0 }, { value: 7, tiebreak: 7 }], runner_up: [{ value: 7, tiebreak: 7 }, { value: 6, tiebreak: 5 }] } });
  assert.equal(resultSummary(result), "Champion Match winner · Runner-up Runner-up · 6(0)–7(7), 7(7)–6(5) · Final");
  assert.equal(resultSummary(final({ status: "walkover" })), "Champion Match winner · Runner-up Runner-up · Walkover");
  assert.equal(resultSummary(final({ status: "retired", score: { winner: [{ value: 2 }], runner_up: [{ value: 0 }] } })), "Champion Match winner · Runner-up Runner-up · 2–0 · Retired");
});

test("missing results stay empty rather than inventing outcome text", () => {
  assert.equal(resultSummary(), "");
  assert.equal(resultSummary(null), "");
});
