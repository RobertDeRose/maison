import type { CodeBlock, Heading } from "./markdown.js";

export type Focus = "body" | "toc";

export interface TimerScheduler {
	setTimeout(callback: () => void, delayMs: number): unknown;
	clearTimeout(handle: unknown): void;
}

export class NumericJumpBuffer {
	private value = "";
	private handle: unknown;

	constructor(
		private readonly scheduler: TimerScheduler,
		private readonly onCommit: (value: string) => void,
	) {}

	push(char: string): void {
		if (!/^[0-9.]$/.test(char)) return;

		this.value += char;
		if (this.handle !== undefined) this.scheduler.clearTimeout(this.handle);

		const delayMs =
			this.value.length === 1 ? 250 : this.value.endsWith(".") ? 700 : 450;
		this.handle = this.scheduler.setTimeout(() => {
			const value = this.value;
			this.value = "";
			this.handle = undefined;
			if (value) this.onCommit(value);
		}, delayMs);
	}

	cancel(): void {
		if (this.handle !== undefined) this.scheduler.clearTimeout(this.handle);
		this.handle = undefined;
		this.value = "";
	}
}

export interface PagerLayout {
	showToc: boolean;
	tocWidth: number;
	gap: number;
	bodyWidth: number;
	contentWidth: number;
}

const MIN_TOC_TERMINAL_WIDTH = 100;
const MAX_TOC_WIDTH = 32;

export function calculatePagerLayout(width: number): PagerLayout {
	const showToc = width >= MIN_TOC_TERMINAL_WIDTH;
	const tocWidth = showToc
		? Math.min(MAX_TOC_WIDTH, Math.max(20, Math.floor(width * 0.2)))
		: 0;
	const gap = showToc ? 1 : 0;
	const bodyWidth = Math.max(30, width - tocWidth - gap);
	return { showToc, tocWidth, gap, bodyWidth, contentWidth: bodyWidth - 4 };
}

export class PagerNavigation {
	private _scroll = 0;
	private _selectedHeading = 0;
	private _focus: Focus = "body";
	private _selectedCodeBlock = 0;
	private expandedDepthByTop = new Map<string, number>();
	private headings: Heading[] = [];
	private codeBlocks: CodeBlock[] = [];
	private lineCount = 0;
	private bodyHeight = 0;

	constructor(
		headings: Heading[],
		codeBlocks: CodeBlock[],
		lineCount: number,
		bodyHeight: number,
	) {
		this.updateDocument(headings, codeBlocks, lineCount, bodyHeight);
	}

	get scroll(): number {
		return this._scroll;
	}

	get selectedHeading(): number {
		return this._selectedHeading;
	}

	get focus(): Focus {
		return this._focus;
	}

	get selectedCodeBlock(): number {
		return this._selectedCodeBlock;
	}

	maxScroll(): number {
		return Math.max(0, this.lineCount - this.bodyHeight);
	}

	updateDocument(
		headings: Heading[],
		codeBlocks: CodeBlock[],
		lineCount: number,
		bodyHeight: number,
	): void {
		this.headings = headings;
		this.codeBlocks = codeBlocks;
		this.lineCount = lineCount;
		this.bodyHeight = bodyHeight;
		this.clampState();
	}

	setFocus(focus: Focus): void {
		this._focus = focus;
	}

	toggleFocus(): void {
		this._focus = this._focus === "body" ? "toc" : "body";
	}

	scrollBy(n: number): void {
		this._scroll = Math.max(0, Math.min(this._scroll + n, this.maxScroll()));
		this.syncTocToScroll();
		this.syncCodeBlockToViewport();
	}

	goHome(): void {
		this._scroll = 0;
		this.syncTocToScroll();
		this.syncCodeBlockToViewport();
	}

	goEnd(): void {
		this._scroll = this.maxScroll();
		this.syncTocToScroll();
		this.syncCodeBlockToViewport();
	}

	selectCodeBlock(delta: number): void {
		const blocks = this.codeBlocks;
		if (blocks.length === 0) return;

		this._selectedCodeBlock =
			(this._selectedCodeBlock + delta + blocks.length) % blocks.length;
		const line = blocks[this._selectedCodeBlock]!.renderLine;
		if (line < 0) return;

		if (line < this._scroll) this._scroll = line;
		else if (line >= this._scroll + this.bodyHeight)
			this._scroll = line - this.bodyHeight + 1;
		this._scroll = Math.max(0, Math.min(this._scroll, this.maxScroll()));
		this.syncTocToScroll();
	}

	syncCodeBlockToViewport(): void {
		const blocks = this.codeBlocks;
		if (blocks.length === 0) return;

		const viewportEnd = this._scroll + this.bodyHeight - 1;
		const selectedLine = blocks[this._selectedCodeBlock]?.renderLine ?? -1;
		if (selectedLine >= this._scroll && selectedLine <= viewportEnd) return;

		const visible = blocks
			.map((block, index) => ({ index, line: block.renderLine }))
			.filter(({ line }) => line >= this._scroll && line <= viewportEnd);
		if (visible.length === 0) return;

		const center = this._scroll + this.bodyHeight / 2;
		visible.sort(
			(a, b) => Math.abs(a.line - center) - Math.abs(b.line - center),
		);
		this._selectedCodeBlock = visible[0]!.index;
	}

	performNumberJump(buf: string): void {
		const normalized = buf.replace(/\.$/, "");
		if (!normalized) return;
		const toc = this.getTocHeadings();

		const exact = toc.findIndex(
			(heading) => this.getTocNumber(heading) === normalized,
		);
		if (exact >= 0) {
			this._selectedHeading = exact;
			this.jumpToSelected();
			return;
		}

		if (!normalized.includes(".")) {
			const index = Number(normalized) - 1;
			if (index >= 0 && index < toc.length) {
				this._selectedHeading = index;
				this.jumpToSelected();
			}
			return;
		}

		const prefix = toc.findIndex((heading) =>
			this.getTocNumber(heading)?.startsWith(normalized),
		);
		if (prefix >= 0) {
			this._selectedHeading = prefix;
			this.jumpToSelected();
		}
	}

	moveToc(n: number): void {
		const tocHeadings = this.getTocHeadings();
		if (tocHeadings.length === 0) return;
		this._selectedHeading = Math.max(
			0,
			Math.min(this._selectedHeading + n, tocHeadings.length - 1),
		);
		this.jumpToSelected(false);
	}

	getTocHeadings(): Heading[] {
		const tocHeadings = this.headings.filter((heading) => heading.level <= 3);
		const rootLevel = this.getTocRootLevel();
		const singleH1 = this.getSingleH1Heading();
		const visible: Heading[] = [];

		if (singleH1) visible.push(singleH1);

		for (const heading of tocHeadings) {
			if (heading === singleH1) continue;
			if (heading.level === rootLevel) {
				visible.push(heading);
				continue;
			}
			if (heading.level < rootLevel) continue;
			const top = this.getTopKey(heading);
			const depth = this.expandedDepthByTop.get(top) ?? rootLevel;
			if (heading.level <= depth) visible.push(heading);
		}
		return visible;
	}

	getSingleH1Heading(): Heading | undefined {
		const h1Headings = this.headings.filter((heading) => heading.level === 1);
		return h1Headings.length === 1 ? h1Headings[0] : undefined;
	}

	getTocNumber(heading: Heading): string | undefined {
		const singleH1 = this.getSingleH1Heading();
		if (!heading.number) return undefined;
		if (!singleH1) return heading.number;

		const h1Prefix = singleH1.number ? `${singleH1.number}.` : undefined;
		if (h1Prefix && heading.number.startsWith(h1Prefix))
			return heading.number.slice(h1Prefix.length);
		return heading.number;
	}

	getExpandedDepth(heading: Heading): number {
		if (heading === this.getSingleH1Heading()) return this.getTocRootLevel();
		return (
			this.expandedDepthByTop.get(this.getTopKey(heading)) ??
			this.getTocRootLevel()
		);
	}

	hasChildren(heading: Heading): boolean {
		if (!heading.number) return false;
		const prefix = `${heading.number}.`;
		return this.headings.some(
			(candidate) =>
				candidate.level <= 3 &&
				candidate.level > heading.level &&
				candidate.number?.startsWith(prefix),
		);
	}

	expandCurrent(): void {
		const heading = this.getTocHeadings()[this._selectedHeading];
		if (!heading) return;
		const top = this.getTopKey(heading);
		const current = this.expandedDepthByTop.get(top) ?? this.getTocRootLevel();
		this.expandedDepthByTop.set(
			top,
			Math.min(3, Math.max(current + 1, heading.level + 1)),
		);
		this._selectedHeading = this.findVisibleIndexForHeading(heading);
		this.jumpToSelected(false);
	}

	collapseCurrent(): void {
		const heading = this.getTocHeadings()[this._selectedHeading];
		if (!heading) return;
		const top = this.getTopKey(heading);
		const current = this.expandedDepthByTop.get(top) ?? this.getTocRootLevel();
		const next = Math.max(this.getTocRootLevel(), current - 1);
		this.expandedDepthByTop.set(top, next);

		if (heading.level > next) {
			const topHeading =
				this.headings.find(
					(candidate) =>
						candidate.level === this.getTocRootLevel() &&
						this.getTopKey(candidate) === top,
				) ?? heading;
			this._selectedHeading = this.findVisibleIndexForHeading(topHeading);
		} else {
			this._selectedHeading = this.findVisibleIndexForHeading(heading);
		}
		this.jumpToSelected(false);
	}

	syncTocToScroll(): void {
		if (this._focus === "toc") return;
		const toc = this.getTocHeadings();
		if (toc.length === 0) return;

		let active = 0;
		for (let i = 0; i < toc.length; i++) {
			if (toc[i]!.renderLine <= this._scroll) active = i;
			else break;
		}
		this._selectedHeading = active;
	}

	jumpToSelected(returnFocusToBody = true): void {
		const heading = this.getTocHeadings()[this._selectedHeading];
		if (heading)
			this._scroll = Math.max(
				0,
				Math.min(heading.renderLine, this.maxScroll()),
			);
		if (returnFocusToBody) this._focus = "body";
	}

	private getTocRootLevel(): number {
		const tocHeadings = this.headings.filter((heading) => heading.level <= 3);
		if (tocHeadings.length === 0) return 1;

		const singleH1 = this.getSingleH1Heading();
		if (singleH1) {
			const nonH1Levels = tocHeadings
				.filter((heading) => heading.level > 1)
				.map((heading) => heading.level);
			if (nonH1Levels.length > 0) return Math.min(...nonH1Levels);
		}

		return Math.min(...tocHeadings.map((heading) => heading.level));
	}

	private getTopKey(heading: Heading): string {
		const rootLevel = this.getTocRootLevel();
		let top = heading;
		for (const candidate of this.headings) {
			if (candidate.sourceLine > heading.sourceLine) break;
			if (candidate.level === rootLevel) top = candidate;
		}
		return top.number ?? `${rootLevel}:${top.title}`;
	}

	private findVisibleIndexForHeading(heading: Heading): number {
		const toc = this.getTocHeadings();
		const index = toc.findIndex((candidate) => candidate === heading);
		return index >= 0 ? index : 0;
	}

	private clampState(): void {
		this._scroll = Math.max(0, Math.min(this._scroll, this.maxScroll()));
		const toc = this.getTocHeadings();
		this._selectedHeading =
			toc.length === 0 ? 0 : Math.min(this._selectedHeading, toc.length - 1);
		this._selectedCodeBlock =
			this.codeBlocks.length === 0
				? 0
				: Math.min(this._selectedCodeBlock, this.codeBlocks.length - 1);
	}
}
