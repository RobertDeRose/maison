import assert from "node:assert/strict";
import test from "node:test";

import {
	extractFencedCodeBlocks,
	extractHeadings,
	normalizeMarkdownInput,
	sanitizeFrameLine,
	stripAnsi,
} from "../pager/markdown.js";

test("normalizes line endings without changing Unicode content", () => {
	assert.equal(normalizeMarkdownInput("café\r\n🦄\rnext"), "café\n🦄\nnext");
});

test("sanitizes terminal controls while preserving ANSI styling and Unicode", () => {
	const styled = "\u001b[31mλ\u001b[0m\ttext\r\n\u0000";
	assert.equal(stripAnsi(styled), "λ\ttext\r\n\u0000");
	assert.equal(sanitizeFrameLine(styled), "\u001b[31mλ\u001b[0m  text  ");
});

test("extracts fenced code blocks with normalized source lines", () => {
	const blocks = extractFencedCodeBlocks(
		'# Example\r\n```typescript extra\r\nconst value = "🦄";\r\n```\r\n~~~\r\nplain\r\n~~~',
	);

	assert.deepEqual(
		blocks.map(({ code, language, sourceLine }) => ({
			code,
			language,
			sourceLine,
		})),
		[
			{ code: 'const value = "🦄";', language: "typescript", sourceLine: 1 },
			{ code: "plain", language: undefined, sourceLine: 4 },
		],
	);
});

test("extracts hierarchical heading numbers while respecting explicit numbers", () => {
	const headings = extractHeadings(
		"# Guide\n## Install\n## 2. Deploy\n### Verify\n#### Details",
	);

	assert.deepEqual(
		headings.map(({ level, title, number }) => ({ level, title, number })),
		[
			{ level: 1, title: "Guide", number: "1" },
			{ level: 2, title: "Install", number: "1.1" },
			{ level: 2, title: "Deploy", number: "2" },
			{ level: 3, title: "Verify", number: "2.1" },
			{ level: 4, title: "Details", number: "2.2" },
		],
	);
});
