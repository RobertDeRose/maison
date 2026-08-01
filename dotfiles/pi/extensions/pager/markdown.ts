const ANSI_PATTERN =
	/\u001b\][^\u0007]*(?:\u0007|\u001b\\)|\u001b\[[0-?]*[ -\/]*[@-~]/g;
const ANSI_PREFIX_PATTERN =
	/^(?:\u001b\][^\u0007]*(?:\u0007|\u001b\\)|\u001b\[[0-?]*[ -\/]*[@-~])/;

export type ContentBlock = { type?: string; text?: string };

export type Heading = {
	level: number;
	title: string;
	sourceLine: number;
	renderLine: number;
	number?: string;
	explicitNumber?: string;
};

export type CodeBlock = {
	code: string;
	language?: string;
	sourceLine: number;
	renderLine: number;
	renderEndLine: number;
};

export function normalizeMarkdownInput(s: string): string {
	return s.replace(/\r\n?/g, "\n");
}

export function sanitizeFrameLine(s: string): string {
	let out = "";

	for (let i = 0; i < s.length; ) {
		const ansi = ANSI_PREFIX_PATTERN.exec(s.slice(i));
		if (ansi) {
			out += ansi[0];
			i += ansi[0].length;
			continue;
		}

		const codePoint = s.codePointAt(i);
		if (codePoint === undefined) break;
		const char = String.fromCodePoint(codePoint);
		i += char.length;

		if (char === "\r" || char === "\n") out += " ";
		else if (char === "\t") out += "  ";
		else if ((codePoint >= 0x00 && codePoint <= 0x1f) || codePoint === 0x7f)
			continue;
		else out += char;
	}

	return out;
}

export function stripAnsi(s: string): string {
	return s.replace(ANSI_PATTERN, "");
}

export function extractText(content: unknown): string {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return "";
	return content
		.map((part) => {
			const block = part as ContentBlock;
			return block?.type === "text" && typeof block.text === "string"
				? block.text
				: "";
		})
		.filter(Boolean)
		.join("\n\n");
}

export function isFence(line: string): boolean {
	return /^\s*(```|~~~)/.test(line);
}

export function extractFencedCodeBlocks(markdown: string): CodeBlock[] {
	const source = normalizeMarkdownInput(markdown).split("\n");
	const blocks: CodeBlock[] = [];

	for (let i = 0; i < source.length; i++) {
		const opening = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(source[i]!);
		if (!opening) continue;

		const marker = opening[1]!;
		const language = opening[2]!.trim().split(/\s+/, 1)[0] || undefined;
		const closing = new RegExp(`^ {0,3}${marker[0]}{${marker.length},}\\s*$`);
		let end = i + 1;
		while (end < source.length && !closing.test(source[end]!)) end++;

		blocks.push({
			code: source.slice(i + 1, end).join("\n"),
			language,
			sourceLine: i,
			renderLine: -1,
			renderEndLine: -1,
		});
		i = end;
	}

	return blocks;
}

export function headingFromLine(
	line: string,
): { level: number; title: string } | null {
	const match = /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
	if (!match) return null;
	return { level: match[1]!.length, title: match[2]!.trim() };
}

export function parseHeadingNumber(title: string): {
	explicitNumber?: string;
	title: string;
} {
	// Match common leading numbering: "1 Title", "1. Title", "1.1 Title", "1.1.1) Title".
	const match = /^\s*(\d+(?:\.\d+)*)(?:[\.\)\-])?\s+(.+?)\s*$/.exec(title);
	if (!match) return { title: title.trim() };
	return { explicitNumber: match[1], title: match[2]!.trim() };
}

export function extractHeadings(markdown: string): Heading[] {
	const source = normalizeMarkdownInput(markdown).trimEnd().split("\n");
	const headings: Heading[] = [];
	let inCode = false;

	for (let i = 0; i < source.length; i++) {
		const raw = source[i]!;
		if (isFence(raw)) {
			inCode = !inCode;
			continue;
		}
		if (inCode) continue;

		const heading = headingFromLine(raw);
		if (!heading) continue;
		headings.push({
			...heading,
			...parseHeadingNumber(heading.title),
			sourceLine: i,
			renderLine: -1,
		});
	}

	const counters: number[] = [];
	for (const heading of headings) {
		const level = Math.min(3, heading.level);

		if (heading.explicitNumber) {
			const parts = heading.explicitNumber
				.split(".")
				.map((part) => Number(part))
				.filter((part) => Number.isFinite(part) && part > 0);
			heading.number = heading.explicitNumber;
			for (let i = 0; i < Math.min(3, parts.length); i++)
				counters[i] = parts[i]!;
			for (let i = Math.min(3, parts.length); i < 3; i++) counters[i] = 0;
			continue;
		}

		counters[level - 1] = (counters[level - 1] || 0) + 1;
		for (let i = level; i < 3; i++) counters[i] = 0;
		heading.number = counters
			.slice(0, level)
			.filter((part) => part > 0)
			.join(".");
	}

	return headings;
}

export function normalizeSectionMarkdown(text: string): string {
	const lines = normalizeMarkdownInput(text).split("\n");
	let inCode = false;

	return lines
		.map((line) => {
			if (isFence(line)) {
				inCode = !inCode;
				return line;
			}
			if (inCode) return line;

			const heading = headingFromLine(line);
			if (!heading || heading.level < 3) return line;

			const parsed = parseHeadingNumber(heading.title);
			const title = parsed.explicitNumber
				? `${parsed.explicitNumber} ${parsed.title}`
				: parsed.title;
			return `**${title}**`;
		})
		.join("\n");
}
