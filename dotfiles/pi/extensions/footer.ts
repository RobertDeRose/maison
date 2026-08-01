import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";

function formatTokens(n: number): string {
	if (n < 1000) return `${n}`;
	if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`;
	return `${(n / 1_000_000).toFixed(1)}m`;
}

function joinStyled(parts: string[], separator: string): string {
	return parts.filter(Boolean).join(separator);
}

export default function (pi: ExtensionAPI) {
	pi.on("session_start", (_event, ctx) => {
		if (!ctx.hasUI) return;

		// In markdown-pager mode, the pager is the whole UI and exits Pi on close.
		// Keep the footer out of the way so `md file.md` feels like a standalone pager.
		if (pi.getFlag("pager")) {
			ctx.ui.setFooter(undefined);
			return;
		}

		ctx.ui.setFooter((tui, theme, footerData) => {
			const unsubBranch = footerData.onBranchChange(() => tui.requestRender());

			return {
				dispose: unsubBranch,
				invalidate() {},
				render(width: number): string[] {
					let input = 0;
					let output = 0;
					let cost = 0;

					for (const entry of ctx.sessionManager.getBranch()) {
						if (
							entry.type === "message" &&
							entry.message.role === "assistant"
						) {
							const message = entry.message as AssistantMessage;
							input += message.usage?.input ?? 0;
							output += message.usage?.output ?? 0;
							cost += message.usage?.cost?.total ?? 0;
						}
					}

					const branch = footerData.getGitBranch();
					const statuses = [...footerData.getExtensionStatuses().values()];

					const left = joinStyled(
						[
							theme.fg("accent", "pi"),
							theme.fg("muted", ctx.model?.id ?? "no model"),
							branch
								? theme.fg("syntaxVariable", branch)
								: theme.fg("dim", "no git"),
						],
						theme.fg("dim", "  *  "),
					);

					const usage = theme.fg(
						"dim",
						`↑${formatTokens(input)} ↓${formatTokens(output)} $${cost.toFixed(3)}`,
					);
					const status =
						statuses.length > 0 ? theme.fg("muted", statuses.join("  ")) : "";
					const right = joinStyled([status, usage], theme.fg("dim", "  *  "));

					const pad = " ".repeat(
						Math.max(1, width - visibleWidth(left) - visibleWidth(right)),
					);
					return [truncateToWidth(left + pad + right, width, "")];
				},
			};
		});
	});

	pi.registerCommand("footer", {
		description: "Restore Pi's default footer for this session",
		handler: async (_args, ctx) => {
			ctx.ui.setFooter(undefined);
			ctx.ui.notify("Default Pi footer restored for this session", "info");
		},
	});
}
