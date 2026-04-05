import type {
  Message,
  StreamLogEntry,
  ToolEntry,
  WorkPlanSnapshot,
  WorkItem,
} from "./types";

// ---------------------------------------------------------------------------
// Blob download
// ---------------------------------------------------------------------------

export function downloadFile(
  content: string,
  filename: string,
  mimeType: string,
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  setTimeout(() => {
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, 100);
}

// ---------------------------------------------------------------------------
// Filename helper
// ---------------------------------------------------------------------------

export function buildExportFilename(
  sessionTitle: string | undefined,
  extension: "md" | "json",
): string {
  const datePart = new Date().toISOString().slice(0, 10);
  const slug = sessionTitle
    ? sessionTitle
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "")
        .slice(0, 40)
    : "chat";
  return `${slug}-export-${datePart}.${extension}`;
}

// ---------------------------------------------------------------------------
// Markdown export — private helpers
// ---------------------------------------------------------------------------

function escapeTableCell(text: string): string {
  return text.replace(/\|/g, "\\|").replace(/\n/g, " ");
}

function formatToolEntry(tool: ToolEntry): string {
  const parts: string[] = [`**${tool.name}**`];

  if (tool.args && Object.keys(tool.args).length > 0) {
    parts.push(
      `Arguments:\n\`\`\`json\n${JSON.stringify(tool.args, null, 2)}\n\`\`\``,
    );
  }

  if (tool.output) {
    parts.push(`Output:\n\`\`\`\n${tool.output}\n\`\`\``);
  }

  return parts.join("\n");
}

function formatStreamLogs(logs: StreamLogEntry[]): string {
  const lines: string[] = ["### Agent Activity\n"];

  for (const log of logs) {
    lines.push(`**${log.nodeName}** — ${log.status}`);

    if (log.message) {
      lines.push(`> ${log.message.replace(/\n/g, "\n> ")}\n`);
    }

    if (log.tools && log.tools.length > 0) {
      lines.push("#### Tool Calls\n");
      for (const tool of log.tools) {
        lines.push(formatToolEntry(tool));
        lines.push("");
      }
    }
  }

  return lines.join("\n");
}

function formatWorkPlans(snapshots: WorkPlanSnapshot[]): string {
  const lines: string[] = [];

  for (const snapshot of snapshots) {
    const plan = snapshot.workplan;
    if (!plan) continue;

    const planTitle = snapshot.display_name || plan.summary || "Work Plan";
    lines.push(`### Work Plan: ${planTitle}\n`);

    const items: WorkItem[] = plan.items ? Object.values(plan.items) : [];
    if (items.length === 0) continue;

    lines.push("| Item | Status | Assigned To | Description |");
    lines.push("|------|--------|-------------|-------------|");

    for (const item of items) {
      const title = escapeTableCell(item.title);
      const assignee = item.assigned_uid || "—";
      const desc = item.description ? escapeTableCell(item.description) : "—";
      lines.push(`| ${title} | ${item.status} | ${assignee} | ${desc} |`);
    }
    lines.push("");

    const withResults = items.filter((i) => i.result?.final_summary);
    if (withResults.length > 0) {
      lines.push("#### Work Item Results\n");
      for (const item of withResults) {
        lines.push(`**${item.title}**`);
        lines.push(
          `> ${item.result!.final_summary!.replace(/\n/g, "\n> ")}\n`,
        );
      }
    }
  }

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Markdown export — public
// ---------------------------------------------------------------------------

export function exportSessionAsMarkdown(
  messages: Message[],
  sessionTitle?: string,
): string {
  const lines: string[] = [];

  lines.push("# Chat Export");
  lines.push(`**Exported:** ${new Date().toLocaleString()}`);
  if (sessionTitle) {
    lines.push(`**Session:** ${sessionTitle}`);
  }
  lines.push("\n---\n");

  for (const msg of messages) {
    if (msg.sender === "user") {
      lines.push("## User\n");
      lines.push(msg.content);
    } else {
      lines.push("## Assistant\n");

      if (msg.streamLogs && msg.streamLogs.length > 0) {
        lines.push(formatStreamLogs(msg.streamLogs));
      }

      if (msg.workPlans && msg.workPlans.length > 0) {
        lines.push(formatWorkPlans(msg.workPlans));
      }

      const response = msg.finalAnswer || msg.content;
      if (response) {
        lines.push("### Response\n");
        lines.push(response);
      }
    }

    lines.push("\n---\n");
  }

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// JSON export
// ---------------------------------------------------------------------------

interface CleanedMessage {
  id: string;
  sender: "user" | "ai";
  content: string;
  finalAnswer?: string;
  streamLogs?: Omit<StreamLogEntry, "isExpanded">[];
  workPlans?: Omit<WorkPlanSnapshot, "isExpanded">[];
}

interface ExportPayload {
  exportedAt: string;
  sessionTitle: string | null;
  messages: CleanedMessage[];
}

function stripUiFields(messages: Message[]): CleanedMessage[] {
  return messages.map((msg) => {
    const cleaned: CleanedMessage = {
      id: msg.id,
      sender: msg.sender,
      content: msg.content,
    };

    if (msg.finalAnswer) {
      cleaned.finalAnswer = msg.finalAnswer;
    }

    if (msg.streamLogs && msg.streamLogs.length > 0) {
      cleaned.streamLogs = msg.streamLogs.map(
        ({ isExpanded: _, ...rest }) => rest,
      );
    }

    if (msg.workPlans && msg.workPlans.length > 0) {
      cleaned.workPlans = msg.workPlans.map(
        ({ isExpanded: _, ...rest }) => rest,
      );
    }

    return cleaned;
  });
}

export function exportSessionAsJSON(
  messages: Message[],
  sessionTitle?: string,
): string {
  const payload: ExportPayload = {
    exportedAt: new Date().toISOString(),
    sessionTitle: sessionTitle ?? null,
    messages: stripUiFields(messages),
  };

  return JSON.stringify(payload, null, 2);
}
