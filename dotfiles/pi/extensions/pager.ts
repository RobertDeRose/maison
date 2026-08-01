import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type {
	ExtensionAPI,
	ExtensionCommandContext,
} from "@earendil-works/pi-coding-agent";
import {
	copyToClipboard,
	getMarkdownTheme,
} from "@earendil-works/pi-coding-agent";
import {
	Markdown,
	truncateToWidth as tuiTruncateToWidth,
	visibleWidth as tuiVisibleWidth,
} from "@earendil-works/pi-tui";
import { decodePrintableKey, Key, matchesKey } from "./pager/keys.js";
import {
	type CodeBlock,
	extractFencedCodeBlocks,
	extractHeadings,
	extractText,
	type Heading,
	headingFromLine,
	isFence,
	normalizeMarkdownInput,
	normalizeSectionMarkdown,
	sanitizeFrameLine,
	stripAnsi,
} from "./pager/markdown.js";
import {
	calculatePagerLayout,
	NumericJumpBuffer,
	PagerNavigation,
	type TimerScheduler,
} from "./pager/navigation.js";

type MarkdownCtor = new (
	markdown: string,
	x: number,
	y: number,
	theme: any,
) => { render(width: number): string[] };
type Rendered = {
	lines: string[];
	headings: Heading[];
	codeBlocks: CodeBlock[];
};

function visibleWidth(s: string): number {
	return tuiVisibleWidth(sanitizeFrameLine(s));
}

function truncateToWidth(s: string, width: number, ellipsis = ""): string {
	return tuiTruncateToWidth(sanitizeFrameLine(s), width, ellipsis);
}

function padRight(s: string, width: number): string {
	return s + " ".repeat(Math.max(0, width - visibleWidth(s)));
}

const REAL_TIMER_SCHEDULER: TimerScheduler = {
	setTimeout(callback, delayMs) {
		return setTimeout(callback, delayMs);
	},
	clearTimeout(handle) {
		clearTimeout(handle as ReturnType<typeof setTimeout>);
	},
};

function locateRenderedCodeBlocks(lines: string[], blocks: CodeBlock[]): void {
	let blockIndex = 0;
	let opening = true;

	for (let i = 0; i < lines.length && blockIndex < blocks.length; i++) {
		const line = stripAnsi(lines[i]!).trimEnd();
		if (!line.startsWith("```")) continue;

		if (opening) {
			blocks[blockIndex]!.renderLine = i;
		} else {
			blocks[blockIndex]!.renderEndLine = i;
			blockIndex++;
		}
		opening = !opening;
	}
}

function renderMarkdown(
	markdown: string,
	width: number,
	Markdown: MarkdownCtor,
	mdTheme: any,
): Rendered {
	const source = normalizeMarkdownInput(markdown).trimEnd().split("\n");
	const headings = extractHeadings(markdown);
	const headingIndexes = new Map(
		headings.map((heading, index) => [heading.sourceLine, index]),
	);
	const sections: { start: number; end: number; headingIndex?: number }[] = [];
	let inCode = false;
	let currentStart = 0;
	let currentHeadingIndex: number | undefined;

	for (let i = 0; i < source.length; i++) {
		const raw = source[i]!;
		if (isFence(raw)) {
			inCode = !inCode;
			continue;
		}
		if (inCode) continue;

		const heading = headingFromLine(raw);
		if (!heading) continue;

		if (i > currentStart || currentHeadingIndex !== undefined) {
			sections.push({
				start: currentStart,
				end: i,
				headingIndex: currentHeadingIndex,
			});
		}

		currentStart = i;
		currentHeadingIndex = headingIndexes.get(i);
	}

	sections.push({
		start: currentStart,
		end: source.length,
		headingIndex: currentHeadingIndex,
	});

	const lines: string[] = [];
	for (const section of sections) {
		if (section.headingIndex !== undefined) {
			headings[section.headingIndex]!.renderLine = lines.length;
		}

		const text = source.slice(section.start, section.end).join("\n");
		if (!text.trim()) continue;

		if (lines.length > 0 && lines[lines.length - 1] !== "") {
			lines.push("");
		}

		const rendered = new Markdown(
			normalizeSectionMarkdown(text),
			0,
			0,
			mdTheme,
		).render(width);
		lines.push(...rendered);
	}

	const codeBlocks = extractFencedCodeBlocks(markdown);
	locateRenderedCodeBlocks(lines, codeBlocks);

	if (headings.length === 0) {
		headings.push({
			level: 1,
			title: "Response",
			sourceLine: 0,
			renderLine: 0,
			number: "1",
		});
	}

	return { lines, headings, codeBlocks };
}

export class MarkdownPager {
	private readonly navigation: PagerNavigation;
	private readonly numberBuffer: NumericJumpBuffer;
	private readonly scheduler: TimerScheduler;
	private cachedWidth = 0;
	private rendered: Rendered = { lines: [], headings: [], codeBlocks: [] };
	private closed = false;
	private copyFeedback?: { index: number; status: "copied" | "failed" };
	private copyTimer: unknown;

	constructor(
		private markdown: string,
		private theme: any,
		private closePager: () => void,
		private requestRender: () => void,
		private reservedRows: number,
		private Markdown: MarkdownCtor,
		private mdTheme: any,
		private copyText: (text: string) => Promise<void> = copyToClipboard,
		scheduler: TimerScheduler = REAL_TIMER_SCHEDULER,
	) {
		this.scheduler = scheduler;
		this.navigation = new PagerNavigation([], [], 0, 0);
		this.numberBuffer = new NumericJumpBuffer(scheduler, (value) => {
			this.navigation.performNumberJump(value);
			this.requestRender();
		});
	}

	private close() {
		this.closed = true;
		this.numberBuffer.cancel();
		if (this.copyTimer !== undefined) {
			this.scheduler.clearTimeout(this.copyTimer);
			this.copyTimer = undefined;
		}
		this.closePager();
	}

	private bodyHeight(): number {
		// Use the whole terminal for the pager frame. The frame itself consumes one
		// top and one bottom border row; any lower editor/footer chrome is hidden
		// while the pager is open.
		return Math.max(0, (process.stdout.rows || 34) - this.reservedRows - 2);
	}

	render(width: number): string[] {
		const layout = calculatePagerLayout(width);
		const bodyHeight = this.bodyHeight();

		if (this.cachedWidth !== layout.contentWidth) {
			this.rendered = renderMarkdown(
				this.markdown,
				layout.contentWidth,
				this.Markdown,
				this.mdTheme,
			);
			this.cachedWidth = layout.contentWidth;
		}

		this.navigation.updateDocument(
			this.rendered.headings,
			this.rendered.codeBlocks,
			this.rendered.lines.length,
			bodyHeight,
		);
		this.navigation.syncTocToScroll();
		this.navigation.syncCodeBlockToViewport();

		const top = this.theme.fg(
			"borderAccent",
			`╭${"─".repeat(layout.bodyWidth - 2)}╮`,
		);
		const helpText =
			this.navigation.focus === "toc"
				? "TOC · ↑↓/jk select · ←/→ collapse/expand · enter jump · tab body · q close"
				: "BODY · ↑↓/jk scroll · ←/→ code · c copy · tab toc · q close";
		const bottom = this.theme.fg(
			"borderAccent",
			`╰─ ${helpText} ${"─".repeat(Math.max(0, layout.bodyWidth - visibleWidth(helpText) - 5))}╯`,
		);

		const bodyLines: string[] = [top];
		for (let i = 0; i < bodyHeight; i++) {
			const renderLine = this.navigation.scroll + i;
			const line = this.decorateCodeFence(
				this.rendered.lines[renderLine] ?? "",
				renderLine,
				layout.contentWidth,
			);
			bodyLines.push(
				this.theme.fg("border", "│ ") +
					padRight(
						truncateToWidth(line, layout.contentWidth, "…"),
						layout.contentWidth,
					) +
					this.theme.fg("border", " │"),
			);
		}
		bodyLines.push(truncateToWidth(bottom, layout.bodyWidth, ""));

		if (!layout.showToc)
			return bodyLines.map((line) =>
				padRight(truncateToWidth(line, width, ""), width),
			);

		const tocLines = this.renderToc(layout.tocWidth, bodyHeight + 2);
		return bodyLines.map((line, i) => {
			const body = padRight(
				truncateToWidth(line, layout.bodyWidth, ""),
				layout.bodyWidth,
			);
			const toc = padRight(
				truncateToWidth(tocLines[i] ?? "", layout.tocWidth, ""),
				layout.tocWidth,
			);
			return padRight(truncateToWidth(`${body} ${toc}`, width, ""), width);
		});
	}

	private decorateCodeFence(
		line: string,
		renderLine: number,
		width: number,
	): string {
		const index = this.rendered.codeBlocks.findIndex(
			(block) => block.renderLine === renderLine,
		);
		if (index < 0 || index !== this.navigation.selectedCodeBlock) return line;

		const feedback =
			this.copyFeedback?.index === index ? this.copyFeedback.status : undefined;
		const label =
			feedback === "copied"
				? this.theme.fg("success", "[copied]")
				: feedback === "failed"
					? this.theme.fg("error", "[copy failed]")
					: this.theme.fg("accent", `[${this.theme.underline("c")}opy]`);
		const fence = line.replace(/\s+$/, "");
		const fenceWidth = Math.max(0, width - visibleWidth(label) - 1);
		return padRight(
			`${truncateToWidth(fence, fenceWidth, "…")} ${label}`,
			width,
		);
	}

	private renderToc(width: number, height: number): string[] {
		const inner = width - 4;
		const lines: string[] = [
			this.theme.fg(
				"borderAccent",
				`╭─ TOC ${"─".repeat(Math.max(0, width - 8))}╮`,
			),
		];
		const tocHeadings = this.navigation.getTocHeadings();
		const visibleItems = Math.max(1, height - 2);
		const start = Math.max(
			0,
			Math.min(
				this.navigation.selectedHeading - Math.floor(visibleItems / 2),
				tocHeadings.length - visibleItems,
			),
		);

		for (let i = 0; i < visibleItems; i++) {
			const idx = start + i;
			const heading = tocHeadings[idx];
			let text = "";
			if (heading) {
				const selected = idx === this.navigation.selectedHeading;
				const marker = selected ? "› " : "  ";
				const singleH1 = heading === this.navigation.getSingleH1Heading();
				const control =
					!singleH1 && heading.level < 3 && this.navigation.hasChildren(heading)
						? this.navigation.getExpandedDepth(heading) > heading.level
							? "▾ "
							: "▸ "
						: "  ";
				const tocNumber = this.navigation.getTocNumber(heading);
				const number = singleH1
					? ""
					: tocNumber
						? `${tocNumber} `
						: `${idx + 1}. `;
				text = marker + control + number + heading.title;
				text = selected
					? this.theme.fg("accent", truncateToWidth(text, inner, "…"))
					: this.theme.fg("muted", truncateToWidth(text, inner, "…"));
			}
			lines.push(
				this.theme.fg("border", "│ ") +
					padRight(text, inner) +
					this.theme.fg("border", " │"),
			);
		}
		lines.push(this.theme.fg("borderAccent", `╰${"─".repeat(width - 2)}╯`));
		return lines;
	}

	handleInput(data: string): void {
		const bodyHeight = this.bodyHeight();
		const page = Math.max(1, Math.floor(bodyHeight / 2));
		const printable =
			decodePrintableKey(data) ?? (data.length === 1 ? data : undefined);

		if (printable && /^[0-9\.]$/.test(printable)) {
			this.numberBuffer.push(printable);
			this.requestRender();
			return;
		}

		this.numberBuffer.cancel();
		const showToc = calculatePagerLayout(process.stdout.columns || 100).showToc;

		if (matchesKey(data, Key.escape) || printable === "q" || printable === "Q")
			this.close();
		else if (matchesKey(data, Key.tab) && showToc)
			this.navigation.toggleFocus();
		else if (matchesKey(data, Key.enter) && this.navigation.focus === "toc")
			this.navigation.jumpToSelected();
		else if (matchesKey(data, Key.right)) {
			this.navigation.focus === "toc"
				? this.navigation.expandCurrent()
				: this.navigation.selectCodeBlock(1);
		} else if (matchesKey(data, Key.left)) {
			this.navigation.focus === "toc"
				? this.navigation.collapseCurrent()
				: this.navigation.selectCodeBlock(-1);
		} else if (printable === "c" && this.navigation.focus === "body")
			this.copySelectedCodeBlock();
		else if (matchesKey(data, Key.down) || printable === "j") {
			this.navigation.focus === "toc"
				? this.navigation.moveToc(1)
				: this.navigation.scrollBy(1);
		} else if (matchesKey(data, Key.up) || printable === "k") {
			this.navigation.focus === "toc"
				? this.navigation.moveToc(-1)
				: this.navigation.scrollBy(-1);
		} else if (matchesKey(data, Key.pageDown) || matchesKey(data, Key.space))
			this.navigation.scrollBy(page);
		else if (matchesKey(data, Key.pageUp)) this.navigation.scrollBy(-page);
		else if (matchesKey(data, Key.home) || printable === "g")
			this.navigation.goHome();
		else if (matchesKey(data, Key.end) || printable === "G")
			this.navigation.goEnd();

		this.requestRender();
	}

	private copySelectedCodeBlock() {
		const index = this.navigation.selectedCodeBlock;
		const block = this.rendered.codeBlocks[index];
		if (!block) return;

		void this.copyText(block.code).then(
			() => this.showCopyFeedback(index, "copied"),
			() => this.showCopyFeedback(index, "failed"),
		);
	}

	private showCopyFeedback(index: number, status: "copied" | "failed") {
		if (this.closed) return;
		if (this.copyTimer !== undefined)
			this.scheduler.clearTimeout(this.copyTimer);
		this.copyFeedback = { index, status };
		this.copyTimer = this.scheduler.setTimeout(() => {
			this.copyFeedback = undefined;
			this.copyTimer = undefined;
			this.requestRender();
		}, 1200);
		this.requestRender();
	}

	invalidate(): void {
		this.cachedWidth = 0;
	}
}

export default function (pi: ExtensionAPI) {
	let latest = "";
	let pagerOpen = false;

	function restoreCursor() {
		if (process.stdout.isTTY) process.stdout.write("\x1b[?25h");
	}

	pi.registerFlag("pager", {
		description: "Open a Markdown file directly in the pager on startup",
		type: "string",
	});

	pi.registerFlag("no-pager-auto", {
		description:
			"Disable automatically opening the pager for responses taller than the current view",
		type: "boolean",
		default: false,
	});

	function hideFooter(ctx: any) {
		ctx.ui.setFooter(() => ({
			invalidate() {},
			render() {
				return [];
			},
		}));
	}

	// Helper that installs a pager footer renderer and returns a restore function.
	function installPagerFooter(ctx: any, renderFn: () => string[]) {
		ctx.ui.setFooter(() => ({
			invalidate() {},
			render() {
				return renderFn();
			},
		}));
		return () => ctx.ui.setFooter(undefined);
	}

	async function openPager(
		ctx: any,
		markdown: string,
		options: { shutdownOnClose?: boolean } = {},
	) {
		if (!ctx.hasUI || pagerOpen) return;
		pagerOpen = true;
		let restoreFooter: (() => void) | undefined;
		try {
			restoreFooter = installPagerFooter(ctx, () => []);
			const reservedRows = 0;
			const mdTheme = getMarkdownTheme();
			await ctx.ui.custom(
				(tui: any, theme: any, _keybindings: any, done: () => void) => {
					const pager = new MarkdownPager(
						markdown,
						theme,
						done,
						() => tui.requestRender(true),
						reservedRows,
						Markdown,
						mdTheme,
					);
					setTimeout(() => tui.requestRender(true), 0);
					return pager;
				},
			);
			if (options.shutdownOnClose) {
				restoreCursor();
				ctx.shutdown();
				setTimeout(() => {
					restoreCursor();
					process.exit(0);
				}, 0);
			}
		} finally {
			try {
				restoreFooter?.();
				ctx.ui.requestRender?.();
			} catch {}
			pagerOpen = false;
		}
	}

	function scheduleOpenPager(ctx: any, markdown: string) {
		setTimeout(() => {
			void openPager(ctx, markdown).catch((error) => {
				ctx.ui.notify(`Could not open pager: ${error}`, "error");
			});
		}, 0);
	}

	function isTallerThanCurrentView(markdown: string): boolean {
		const rows = process.stdout.rows || 34;
		const cols = process.stdout.columns || 100;
		const usableRows = Math.max(10, rows - 4);
		const approxBodyWidth = Math.max(40, Math.floor(cols * 0.78) - 4);
		let visualLines = 0;

		for (const line of normalizeMarkdownInput(markdown).split("\n")) {
			const width = Math.max(1, visibleWidth(line));
			visualLines += Math.max(1, Math.ceil(width / approxBodyWidth));
			if (visualLines > usableRows) return true;
		}

		return false;
	}

	pi.on("session_start", (_event, ctx) => {
		const pagerFile = pi.getFlag("pager") as string | undefined;
		if (!pagerFile) return;

		setTimeout(() => {
			void (async () => {
				try {
					hideFooter(ctx);
					const path = resolve(pagerFile);
					const markdown = readFileSync(path, "utf8");
					latest = markdown;
					await openPager(ctx, markdown, { shutdownOnClose: true });
				} catch (error) {
					ctx.ui.notify(`Could not open pager file: ${error}`, "error");
				}
			})();
		}, 0);
	});

	pi.on("message_end", (event, ctx) => {
		if (event.message.role !== "assistant") return;
		const text = extractText((event.message as any).content).trim();
		if (!text) return;

		latest = text;

		if (!pi.getFlag("no-pager-auto") && isTallerThanCurrentView(text)) {
			scheduleOpenPager(ctx, text);
		}
	});

	const pageCommand = {
		description:
			"Open latest assistant response, or a Markdown file: /page [path/to/file.md]",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			if (!ctx.hasUI) return;
			const file = args.trim();

			if (file) {
				try {
					const markdown = readFileSync(resolve(file), "utf8");
					latest = markdown;
					await openPager(ctx, markdown);
				} catch (error) {
					ctx.ui.notify(`Could not open file: ${error}`, "error");
				}
				return;
			}

			if (!latest) {
				ctx.ui.notify("No assistant response captured yet", "warning");
				return;
			}

			await openPager(ctx, latest);
		},
	};

	pi.registerCommand("pager", pageCommand);
	pi.registerCommand("page", {
		...pageCommand,
		description: "Alias for /pager",
	});
}
