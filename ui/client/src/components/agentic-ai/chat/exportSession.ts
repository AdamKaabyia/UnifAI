import type {
  Message,
  StreamLogEntry,
  ToolEntry,
  WorkPlanSnapshot,
  WorkItem,
} from "./types";

// ---------------------------------------------------------------------------
// Download helper
// ---------------------------------------------------------------------------

export function downloadFile(
  content: string,
  filename: string,
  mimeType: string,
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  setTimeout(() => {
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, 100);
}

// ---------------------------------------------------------------------------
// Markdown export
// ---------------------------------------------------------------------------

function formatToolEntry(tool: ToolEntry): string {
  const parts: string[] = [`**${tool.name}**`];

  if (tool.args && Object.keys(tool.args).length > 0) {
    parts.push(`Arguments:\n\`\`\`json\n${JSON.stringify(tool.args, null, 2)}\n\`\`\``);
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
    const planTitle = snapshot.display_name || plan.summary || "Work Plan";
    lines.push(`### Work Plan: ${planTitle}\n`);

    const items = Object.values(plan.items);
    if (items.length > 0) {
      lines.push("| Item | Status | Assigned To | Description |");
      lines.push("|------|--------|-------------|-------------|");
      for (const item of items) {
        const assignee = item.assigned_uid || "—";
        const desc = item.description
          ? item.description.replace(/\|/g, "\\|").replace(/\n/g, " ")
          : "—";
        lines.push(
          `| ${item.title.replace(/\|/g, "\\|")} | ${item.status} | ${assignee} | ${desc} |`,
        );
      }
      lines.push("");

      const completedWithResults = items.filter(
        (i: WorkItem) => i.result?.final_summary,
      );
      if (completedWithResults.length > 0) {
        lines.push("#### Work Item Results\n");
        for (const item of completedWithResults) {
          lines.push(`**${item.title}**`);
          lines.push(`> ${item.result!.final_summary!.replace(/\n/g, "\n> ")}\n`);
        }
      }
    }
  }

  return lines.join("\n");
}

export function exportSessionAsMarkdown(
  messages: Message[],
  sessionTitle?: string,
): string {
  const lines: string[] = [];
  const timestamp = new Date().toLocaleString();

  lines.push("# Chat Export");
  lines.push(`**Exported:** ${timestamp}`);
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

      const responseText = msg.finalAnswer || msg.content;
      if (responseText) {
        lines.push("### Response\n");
        lines.push(responseText);
      }
    }

    lines.push("\n---\n");
  }

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// JSON export
// ---------------------------------------------------------------------------

function stripUiFields(messages: Message[]): any[] {
  return messages.map((msg) => {
    const cleaned: any = {
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
  const payload = {
    exportedAt: new Date().toISOString(),
    sessionTitle: sessionTitle || null,
    messages: stripUiFields(messages),
  };

  return JSON.stringify(payload, null, 2);
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
