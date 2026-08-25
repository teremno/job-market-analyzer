import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { formatDate } from "./format.ts";

describe("formatDate", () => {
  it("renders an em dash for null, empty, and invalid values", () => {
    assert.equal(formatDate(null), "—");
    assert.equal(formatDate(""), "—");
    assert.equal(formatDate("not-a-date"), "—");
  });

  it("formats ISO timestamps on the UTC calendar day", () => {
    assert.equal(formatDate("2026-08-25T10:00:00.000000Z"), "Aug 25, 2026");
    assert.equal(formatDate("2026-08-25T23:59:59Z"), "Aug 25, 2026");
    assert.equal(formatDate("2026-01-01T00:00:00Z"), "Jan 1, 2026");
  });
});
