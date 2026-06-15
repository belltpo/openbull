/**
 * Visual lifecycle timeline for a Futures-Risk position:
 *   Created → Order Executed → Target 1 → Break-Even → Target 2 → … → Closed
 * Nodes light up as each milestone is reached.
 */
import { Check, Circle, Flag, Play, ShieldCheck, Target, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FrTrade } from "@/types/futuresRisk";

type StepState = "done" | "current" | "todo" | "failed";

interface Step {
  key: string;
  label: string;
  state: StepState;
  icon: React.ReactNode;
  sub?: string;
}

function buildSteps(trade: FrTrade): Step[] {
  const steps: Step[] = [];
  const placed = trade.status !== "draft";
  const closed = ["completed", "stopped", "cancelled"].includes(trade.status);
  const stopped = trade.status === "stopped";

  steps.push({ key: "created", label: "Created", state: "done", icon: <Flag className="h-3.5 w-3.5" /> });
  steps.push({
    key: "executed",
    label: placed ? "Executed" : "Pending",
    state: placed ? "done" : "current",
    icon: <Play className="h-3.5 w-3.5" />,
    sub: placed ? `@ ${trade.entry_futures_price}` : "draft",
  });

  // Break-even activates once the SL has trailed off its initial price.
  const breakevenOn = trade.sl_basis !== "initial";
  let breakevenInserted = false;

  trade.targets.forEach((t) => {
    const hit = t.status === "hit";
    steps.push({
      key: `t${t.seq}`,
      label: `Target ${t.seq}`,
      state: hit ? "done" : closed ? "todo" : "current",
      icon: <Target className="h-3.5 w-3.5" />,
      sub: `${t.trigger_price}`,
    });
    // Insert the Break-Even node right after Target 1.
    if (t.seq === 1 && !breakevenInserted) {
      breakevenInserted = true;
      steps.push({
        key: "breakeven",
        label: "Break-Even",
        state: breakevenOn ? "done" : hit ? "current" : "todo",
        icon: <ShieldCheck className="h-3.5 w-3.5" />,
        sub: breakevenOn ? `SL ${trade.sl_price}` : undefined,
      });
    }
  });

  steps.push({
    key: "closed",
    label: stopped ? "Stopped" : closed ? "Closed" : "Open",
    state: stopped ? "failed" : closed ? "done" : "todo",
    icon: stopped ? <X className="h-3.5 w-3.5" /> : closed ? <Check className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />,
  });

  return steps;
}

const stateRing: Record<StepState, string> = {
  done: "border-emerald-400/60 bg-emerald-400/15 text-emerald-600 dark:text-emerald-300",
  current: "border-primary/60 bg-primary/15 text-primary",
  todo: "border-border bg-muted/40 text-muted-foreground",
  failed: "border-red-400/60 bg-red-400/15 text-red-600 dark:text-red-300",
};

export function PositionTimeline({ trade }: { trade: FrTrade }) {
  const steps = buildSteps(trade);
  return (
    <div className="flex items-start gap-0 overflow-x-auto pb-1">
      {steps.map((s, i) => (
        <div key={s.key} className="flex min-w-0 items-start">
          <div className="flex w-16 flex-col items-center text-center sm:w-[4.5rem]">
            <div
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full border transition-colors",
                stateRing[s.state],
                s.state === "current" && "fr-dot-live",
              )}
            >
              {s.icon}
            </div>
            <span className="mt-1 line-clamp-1 text-[10px] font-medium text-foreground/80">{s.label}</span>
            {s.sub && <span className="text-[9px] tabular-nums text-muted-foreground">{s.sub}</span>}
          </div>
          {i < steps.length - 1 && (
            <div
              className={cn(
                "mt-3.5 h-0.5 w-4 shrink-0 rounded-full sm:w-6",
                steps[i + 1].state === "done" || s.state === "done" ? "bg-emerald-400/50" : "bg-border",
              )}
            />
          )}
        </div>
      ))}
    </div>
  );
}
