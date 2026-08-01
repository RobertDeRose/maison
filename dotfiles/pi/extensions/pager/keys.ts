export type KeyName =
	| "escape"
	| "tab"
	| "enter"
	| "right"
	| "left"
	| "down"
	| "up"
	| "pageDown"
	| "pageUp"
	| "home"
	| "end"
	| "space";

export const Key: Record<KeyName, KeyName> = {
	escape: "escape",
	tab: "tab",
	enter: "enter",
	right: "right",
	left: "left",
	down: "down",
	up: "up",
	pageDown: "pageDown",
	pageUp: "pageUp",
	home: "home",
	end: "end",
	space: "space",
};

const KEY_SEQUENCES: Record<KeyName, readonly string[]> = {
	escape: ["\u001b", "esc"],
	tab: ["\t", "tab"],
	enter: ["\r", "\n", "enter", "return"],
	right: ["\u001b[C", "\u001bOC", "right"],
	left: ["\u001b[D", "\u001bOD", "left"],
	down: ["\u001b[B", "\u001bOB", "down"],
	up: ["\u001b[A", "\u001bOA", "up"],
	pageDown: ["\u001b[6~", "pageDown"],
	pageUp: ["\u001b[5~", "pageUp"],
	home: ["\u001b[H", "\u001b[1~", "\u001bOH", "home"],
	end: ["\u001b[F", "\u001b[4~", "\u001bOF", "end"],
	space: [" ", "space"],
};

const CSI_KEY_NAMES: Record<string, KeyName> = {
	A: "up",
	B: "down",
	C: "right",
	D: "left",
	F: "end",
	H: "home",
};
const CSI_TILDE_KEY_NAMES: Record<number, KeyName> = {
	1: "home",
	4: "end",
	5: "pageUp",
	6: "pageDown",
};

export function parseKeyName(data: string): KeyName | undefined {
	for (const [name, sequences] of Object.entries(KEY_SEQUENCES) as [
		KeyName,
		readonly string[],
	][]) {
		if (sequences.includes(data)) return name;
	}
	const csiFinal = /^\u001b\[(?:\d+(?:;[\d:]+)*)?([A-DFH])$/.exec(data);
	if (csiFinal) return CSI_KEY_NAMES[csiFinal[1]!];
	const csiTilde = /^\u001b\[(\d+)(?:;[\d:]+)?~$/.exec(data);
	if (csiTilde) return CSI_TILDE_KEY_NAMES[Number(csiTilde[1])];
	return undefined;
}

export function matchesKey(data: string, key: KeyName): boolean {
	return parseKeyName(data) === key;
}

export function decodePrintableKey(data: string): string | undefined {
	if (data.length === 1 && data >= " " && data !== "\u007f") return data;
	const kitty = /^\u001b\[(\d+)(?:;[\d:]+)?u$/.exec(data);
	if (kitty) {
		const codepoint = Number(kitty[1]);
		if (Number.isFinite(codepoint) && codepoint >= 32) {
			try {
				return String.fromCodePoint(codepoint);
			} catch {
				return undefined;
			}
		}
	}
	const modifyOtherKeys = /^\u001b\[27;(\d+);(\d+)~$/.exec(data);
	if (modifyOtherKeys) {
		const modifier = Number(modifyOtherKeys[1]) - 1;
		const codepoint = Number(modifyOtherKeys[2]);
		if (
			(modifier & ~1) === 0 &&
			Number.isFinite(codepoint) &&
			codepoint >= 32
		) {
			try {
				return String.fromCodePoint(codepoint);
			} catch {
				return undefined;
			}
		}
	}
	return undefined;
}
