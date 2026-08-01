import assert from "node:assert/strict";
import test from "node:test";

import { decodePrintableKey, matchesKey } from "../pager/keys.js";

test("matches named and modified cursor key sequences", () => {
	assert.equal(matchesKey("\u001b[A", "up"), true);
	assert.equal(matchesKey("\u001b[1;2A", "up"), true);
	assert.equal(matchesKey("\u001b[6~", "pageDown"), true);
	assert.equal(matchesKey("not-a-key", "up"), false);
});

test("decodes printable Unicode and terminal keyboard protocols", () => {
	assert.equal(decodePrintableKey("é"), "é");
	assert.equal(decodePrintableKey("\u001b[129449u"), "🦩");
	assert.equal(decodePrintableKey("\u001b[27;2;233~"), "é");
	assert.equal(decodePrintableKey("\u001b[13u"), undefined);
});
