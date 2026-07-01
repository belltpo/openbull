/**
 * Visual lifecycle timeline for a Futures-Risk position:
 * Order Placed -> Stoploss -> Entry -> Target 1 -> Target 2 -> ... -> Closed.
 * Targets are rendered from the per-trade snapshot created at order placement.
 */
import { Check, Circle, ClipboardCheck, Play, Shield, Target, X } from "lucide-react";

import { cn } from "@/lib/utils";
import type { FrTrade } from "@/types/futuresRisk";

type StepState = "done" | "current" | "todo" | "failed";
type StepTone = "neutral" | "red" | "blue" | "green" | "muted";

interface Step {
  key: string;
  label: string;
  state: StepState;
  tone: StepTone;
  icon: React.ReactNode;
  futures?: string;
  option?: string;
}

function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function optLine(liveOpt: number | undefined): string {
  return `Opt LTP ${fmt(liveOpt)}`;
}

function initialSlPrice(trade: FrTrade): number {
  return trade.entry_futures_price - trade.direction * trade.sl_points;
}

function buildSteps(trade: FrTrade, liveOpt: number | undefined): Step[] {
  const steps: Step[] = [];
  const placed = trade.status !== "draft";
  const closed = ["completed", "stopped", "cancelled"].includes(trade.status);
  const stopped = trade.status === "stopped";
  const t1Hit = trade.targets.some((t) => t.seq === 1 && t.status === "hit");
  const nextPendingSeq = trade.targets.find((t) => t.status === "pending")?.seq ?? null;

  steps.push({
    key: "placed",
    label: "Placed",
    state: "done",
    tone: "neutral",
    icon: <ClipboardCheck className="h-3.5 w-3.5" />,
  });

  steps.push({
    key: "initial-sl",
    label: t1Hit ? "Initial SL" : "Stoploss",
    state: t1Hit ? "done" : stopped ? "failed" : placed ? "current" : "todo",
    tone: t1Hit ? "muted" : "red",
    icon: <Shield className="h-3.5 w-3.5" />,
    futures: `Fut ${fmt(t1Hit ? initialSlPrice(trade) : trade.sl_price)}`,
    option: optLine(liveOpt),
  });

  steps.push({
    key: "entry",
    label: t1Hit ? "Stoploss" : placed ? "Entry" : "Entry Pending",
    state: t1Hit && !closed ? "current" : placed ? "done" : "current",
    tone: t1Hit ? "red" : "blue",
    icon: <Play className="h-3.5 w-3.5" />,
    futures: placed ? `Fut ${fmt(trade.entry_futures_price)}` : "Draft",
    option: optLine(liveOpt),
  });

  trade.targets.forEach((target) => {
    const hit = target.status === "hit";
    steps.push({
      key: `t${target.seq}`,
      label: `Target ${target.seq}`,
      state: hit ? "done" : closed ? "todo" : target.seq === nextPendingSeq ? "current" : "todo",
      tone: "green",
      icon: <Target className="h-3.5 w-3.5" />,
      futures: `Fut ${fmt(target.trigger_price)}`,
      option: optLine(liveOpt),
    });
  });

  steps.push({
    key: "closed",
    label: stopped ? "Stopped" : closed ? "Closed" : "Open",
    state: stopped ? "failed" : closed ? "done" : "todo",
    tone: stopped ? "red" : closed ? "green" : "muted",
    icon: stopped ? (
      <X className="h-3.5 w-3.5" />
    ) : closed ? (
      <Check className="h-3.5 w-3.5" />
    ) : (
      <Circle className="h-3.5 w-3.5" />
    ),
  });

  return steps;
}

const toneRing: Record<StepTone, string> = {
  neutral: "border-emerald-400/60 bg-emerald-400/15 text-emerald-600 dark:text-emerald-300",
  red: "border-red-400/70 bg-red-400/15 text-red-600 dark:text-red-300",
  blue: "border-sky-400/70 bg-sky-400/15 text-sky-600 dark:text-sky-300",
  green: "border-emerald-400/70 bg-emerald-400/15 text-emerald-600 dark:text-emerald-300",
  muted: "border-border bg-muted/40 text-muted-foreground",
};

function connectorClass(left: Step, right: Step): string {
  if (left.state === "failed" || right.state === "failed") return "bg-red-400/45";
  if (left.state === "done" || right.state === "done") return "bg-emerald-400/50";
  return "bg-border";
}

export function PositionTimeline({ trade, liveOpt }: { trade: FrTrade; liveOpt?: number }) {
  const steps = buildSteps(trade, liveOpt);

  return (
    <div className="flex items-start gap-0 overflow-x-auto pb-1">
      {steps.map((step, index) => (
        <div key={step.key} className="flex min-w-0 items-start">
          <div className="flex w-[3.9rem] flex-col items-center text-center sm:w-[4.35rem]">
            <div
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-full border transition-colors",
                step.state === "todo" ? toneRing.muted : toneRing[step.tone],
                step.state === "current" && "fr-dot-live",
              )}
            >
              {step.icon}
            </div>
            <span className="mt-1 line-clamp-1 text-[10px] font-semibold leading-tight text-foreground/85">
              {step.label}
            </span>
            {step.futures && <span className="text-[9px] tabular-nums text-muted-foreground">{step.futures}</span>}
            {step.option && <span className="text-[9px] tabular-nums text-muted-foreground">{step.option}</span>}
          </div>
          {index < steps.length - 1 && (
            <div className={cn("mt-3 h-0.5 w-2 shrink-0 rounded-full sm:w-3", connectorClass(step, steps[index + 1]))} />
          )}
        </div>
      ))}
    </div>
  );
}
