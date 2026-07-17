import { toast } from "sonner";

export interface BrokerIssue {
  code: "BROKER_RATE_LIMIT" | "BROKER_AUTH_REQUIRED";
  broker?: string;
  message?: string;
  action_url?: string;
  retry_after_seconds?: number;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object"
    ? (value as Record<string, unknown>)
    : null;
}

export function extractBrokerIssue(value: unknown): BrokerIssue | null {
  const root = asRecord(value);
  if (!root) return null;
  const detail = asRecord(root.detail);
  const candidate = detail ?? root;
  let code = String(candidate.code ?? "");
  const messageText = String(candidate.message ?? candidate.broker_message ?? "").toLowerCase();
  if (!code && (messageText.includes("rate limit") || messageText.includes("too many requests") || messageText.includes("805"))) {
    code = "BROKER_RATE_LIMIT";
  }
  if (!code && (
    messageText.includes("authentication failed") || messageText.includes("token invalid")
    || messageText.includes("invalid or expired") || messageText.includes("unauthorized")
  )) {
    code = "BROKER_AUTH_REQUIRED";
  }
  if (code !== "BROKER_RATE_LIMIT" && code !== "BROKER_AUTH_REQUIRED") return null;
  return {
    code,
    broker: String(candidate.broker ?? ""),
    message: String(candidate.message ?? ""),
    action_url: String(candidate.action_url ?? "/broker/config"),
    retry_after_seconds: Number(candidate.retry_after_seconds ?? 0) || undefined,
  };
}

export function notifyBrokerIssue(value: unknown): BrokerIssue | null {
  const issue = extractBrokerIssue(value);
  if (!issue) return null;
  const fallback = issue.code === "BROKER_RATE_LIMIT"
    ? "Dhan data rate limit reached. Regenerate or re-login the broker API connection."
    : "Broker authentication expired. Re-login the broker connection.";
  toast.error(issue.message || fallback, {
    id: `broker-issue:${issue.broker || "active"}:${issue.code}`,
    duration: Infinity,
    action: {
      label: "Broker settings",
      onClick: () => window.location.assign(issue.action_url || "/broker/config"),
    },
  });
  return issue;
}
