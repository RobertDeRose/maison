import assert from "node:assert/strict";
import test from "node:test";
import type { CodeBlock, Heading } from "../pager/markdown.js";
import {
	calculatePagerLayout,
	NumericJumpBuffer,
	PagerNavigation,
	type TimerScheduler,
} from "../pager/navigation.js";

const headings: Heading[] = [
	{ level: 1, title: "Guide", sourceLine: 0, renderLine: 0, number: "1" },
	{ level: 2, title: "Install", sourceLine: 2, renderLine: 2, number: "1.1" },
	{ level: 2, title: "Deploy", sourceLine: 12, renderLine: 12, number: "1.2" },
	{
		level: 3,
		title: "Verify",
		sourceLine: 16,
		renderLine: 16,
		number: "1.2.1",
	},
];

const codeBlocks: CodeBlock[] = [
	{ code: "first", sourceLine: 4, renderLine: 4, renderEndLine: 6 },
	{ code: "second", sourceLine: 20, renderLine: 20, renderEndLine: 22 },
];

test("clamps scrolling and keeps code-block selection in view", () => {
	const navigation = new PagerNavigation(headings, codeBlocks, 30, 5);

	assert.equal(navigation.maxScroll(), 25);
	navigation.scrollBy(999);
	assert.equal(navigation.scroll, 25);

	navigation.goHome();
	navigation.selectCodeBlock(1);
	assert.equal(navigation.selectedCodeBlock, 1);
	assert.equal(navigation.scroll, 16);

	navigation.selectCodeBlock(1);
	assert.equal(navigation.selectedCodeBlock, 0);
	assert.equal(navigation.scroll, 4);
});

test("jumps through the visible TOC and preserves focus rules", () => {
	const navigation = new PagerNavigation(headings, codeBlocks, 30, 5);

	assert.deepEqual(
		navigation.getTocHeadings().map((heading) => heading.title),
		["Guide", "Install", "Deploy"],
	);
	navigation.performNumberJump("2");
	assert.equal(navigation.selectedHeading, 2);
	assert.equal(navigation.scroll, 12);

	navigation.setFocus("toc");
	navigation.moveToc(1);
	assert.equal(navigation.selectedHeading, 2);
	assert.equal(navigation.focus, "toc");
	navigation.toggleFocus();
	assert.equal(navigation.focus, "body");
});

test("uses deterministic scheduler delays for numeric jumps", () => {
	const scheduler = new FakeScheduler();
	const commits: string[] = [];
	const buffer = new NumericJumpBuffer(scheduler, (value) =>
		commits.push(value),
	);

	buffer.push("1");
	assert.equal(scheduler.lastDelay, 250);
	scheduler.runLatest();
	assert.deepEqual(commits, ["1"]);

	buffer.push("1");
	buffer.push(".");
	assert.equal(scheduler.lastDelay, 700);
	scheduler.runLatest();
	assert.deepEqual(commits, ["1", "1."]);

	buffer.push("2");
	buffer.cancel();
	scheduler.runLatest();
	assert.deepEqual(commits, ["1", "1."]);
});

test("calculates narrow and wide terminal layouts deterministically", () => {
	assert.deepEqual(calculatePagerLayout(99), {
		showToc: false,
		tocWidth: 0,
		gap: 0,
		bodyWidth: 99,
		contentWidth: 95,
	});
	assert.deepEqual(calculatePagerLayout(100), {
		showToc: true,
		tocWidth: 20,
		gap: 1,
		bodyWidth: 79,
		contentWidth: 75,
	});
	assert.equal(calculatePagerLayout(240).tocWidth, 32);
});

class FakeScheduler implements TimerScheduler {
	private nextId = 0;
	private pending = new Map<number, () => void>();
	lastDelay = 0;

	setTimeout(callback: () => void, delayMs: number): number {
		const id = ++this.nextId;
		this.lastDelay = delayMs;
		this.pending.set(id, callback);
		return id;
	}

	clearTimeout(handle: unknown): void {
		this.pending.delete(handle as number);
	}

	runLatest(): void {
		const id = Math.max(...this.pending.keys());
		const callback = this.pending.get(id);
		this.pending.delete(id);
		callback?.();
	}
}
