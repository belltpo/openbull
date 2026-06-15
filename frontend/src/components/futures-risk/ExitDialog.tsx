/**
 * Close a position: full exit, partial exit (specific quantity), or an
 * emergency force-close. Confirmation is required before any order fires.
 */
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, LogOut } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { emergencyExit, exitTrade, partialExit } from "@/api/futuresRisk";
import type { FrTrade } from "@/types/futuresRisk";

type Mode = "full" | "partial" | "emergency";

interface Props {
  trade: FrTrade | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialMode?: Mode;
}

export function ExitDialog({ trade, open, onOpenChange, initialMode = "full" }: Props) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<Mode>("full");
  const [qty, setQty] = useState(0);

  useEffect(() => {
    if (trade) {
      setMode(initialMode);
      setQty(Math.max(trade.lot_size, Math.floor(trade.remaining_qty / 2)));
    }
  }, [trade, initialMode]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!trade) return;
      if (mode === "emergency") return emergencyExit(trade.id);
      if (mode === "partial") return partialExit(trade.id, qty);
      return exitTrade(trade.id);
    },
    onSuccess: () => {
      toast.success(mode === "emergency" ? "Emergency close placed" : "Exit order placed");
      qc.invalidateQueries({ queryKey: ["fr-trades"] });
      qc.invalidateQueries({ queryKey: ["fr-trade-detail", trade?.id] });
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      // @ts-expect-error axios error shape
      toast.error(String(err?.response?.data?.detail ?? "Exit failed"));
    },
  });

  if (!trade) return null;
  const lots = trade.lot_size || 1;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="fr-glass-strong sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <LogOut className="h-4 w-4" /> Close {trade.underlying}
          </DialogTitle>
          <DialogDescription className="font-mono text-xs">
            {trade.option_symbol} · {trade.remaining_qty} qty open
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-1">
          <div className="grid grid-cols-3 gap-2">
            {(["full", "partial", "emergency"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={cn(
                  "rounded-lg border px-2 py-2 text-xs font-medium capitalize transition-colors",
                  mode === m
                    ? m === "emergency"
                      ? "border-red-500 bg-red-500/15 text-red-600 dark:text-red-300"
                      : "border-primary bg-primary/15 text-primary"
                    : "border-border text-muted-foreground hover:bg-muted/50",
                )}
              >
                {m}
              </button>
            ))}
          </div>

          {mode === "partial" && (
            <div className="space-y-1.5">
              <Label className="text-xs">
                Quantity to exit <span className="text-muted-foreground">(multiples of {lots})</span>
              </Label>
              <input
                type="range"
                min={lots}
                max={trade.remaining_qty}
                step={lots}
                value={qty}
                onChange={(e) => setQty(Number(e.target.value))}
                className="w-full"
              />
              <div className="flex items-center justify-between text-xs tabular-nums">
                <span className="text-muted-foreground">{lots}</span>
                <span className="font-semibold">{qty} qty ({Math.round(qty / lots)} lots)</span>
                <span className="text-muted-foreground">{trade.remaining_qty}</span>
              </div>
            </div>
          )}

          {mode === "emergency" && (
            <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2.5 text-xs text-red-600 dark:text-red-300">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>Force-closes the entire remaining position immediately at market. Use only to bail out fast.</span>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
            className={cn(mode === "emergency" && "bg-red-600 text-white hover:bg-red-700")}
            variant={mode === "emergency" ? undefined : "default"}
          >
            Confirm {mode} exit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
