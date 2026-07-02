/**
 * Modify a position before (draft) or after (active) placement.
 * Active trades: Stop-Loss (futures points), pending Targets, Trailing mode.
 * Drafts: the above plus Lots.
 */
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Minus, Plus, Save } from "lucide-react";

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
import { Badge } from "@/components/ui/badge";
import { modifyTrade } from "@/api/futuresRisk";
import type { FrTrade, ModifyTradePayload, TrailingMode } from "@/types/futuresRisk";

interface Props {
  trade: FrTrade | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const inputCls =
  "h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3";

type TargetEditRow = { points: number; exit_pct: number };

function splitExitPercent(count: number): number[] {
  if (count <= 0) return [];
  const base = Math.floor(10000 / count) / 100;
  const values = Array.from({ length: count }, () => base);
  values[count - 1] = Number((100 - values.slice(0, -1).reduce((sum, value) => sum + value, 0)).toFixed(2));
  return values;
}

function autoSplitTargets(rows: TargetEditRow[]): TargetEditRow[] {
  const split = splitExitPercent(rows.filter((row) => row.points > 0).length);
  let splitIndex = 0;
  return rows.map((row) => {
    if (row.points <= 0) return { ...row, exit_pct: 0 };
    return { ...row, exit_pct: split[splitIndex++] ?? 0 };
  });
}

function normalizeTargetRows(rows: TargetEditRow[]): TargetEditRow[] {
  const active = rows.filter((row) => row.points > 0);
  const total = Number(active.reduce((sum, row) => sum + Number(row.exit_pct || 0), 0).toFixed(2));
  return active.length > 0 && Math.abs(total - 100) > 0.01 ? autoSplitTargets(rows) : rows;
}

export function ModifyPositionDialog({ trade, open, onOpenChange }: Props) {
  const qc = useQueryClient();
  const isDraft = trade?.status === "draft";

  const [slPoints, setSlPoints] = useState<string>("");
  const [lots, setLots] = useState(1);
  const [trailing, setTrailing] = useState<TrailingMode | "">("");
  const [targets, setTargets] = useState<TargetEditRow[]>([]);
  const [editTargets, setEditTargets] = useState(false);

  useEffect(() => {
    if (!trade) return;
    setSlPoints(String(trade.sl_points ?? ""));
    setLots(trade.lots);
    setTrailing(trade.trailing_mode ?? "");
    // Only pending targets can be re-shaped; prefill from current snapshot.
    setTargets(trade.targets.filter((t) => t.status !== "hit").map((t) => ({ points: t.points, exit_pct: t.exit_pct })));
    setEditTargets(false);
  }, [trade]);

  const mutation = useMutation({
    mutationFn: (fields: ModifyTradePayload) => modifyTrade(trade!.id, fields),
    onSuccess: () => {
      toast.success("Position updated");
      qc.invalidateQueries({ queryKey: ["fr-trades"] });
      qc.invalidateQueries({ queryKey: ["fr-trade-detail", trade?.id] });
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      // @ts-expect-error axios error shape
      toast.error(String(err?.response?.data?.detail ?? "Update failed"));
    },
  });

  if (!trade) return null;

  const save = () => {
    const fields: ModifyTradePayload = {};
    if (slPoints !== "" && Number(slPoints) > 0) fields.sl_points = Number(slPoints);
    if (trailing) fields.trailing_mode = trailing;
    if (editTargets) fields.targets = normalizeTargetRows(targets.filter((t) => t.points > 0));
    if (isDraft && lots !== trade.lots) fields.lots = lots;
    if (Object.keys(fields).length === 0) {
      toast.error("Nothing changed");
      return;
    }
    mutation.mutate(fields);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="fr-glass-strong sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>Modify {trade.underlying}</span>
            <Badge variant="outline">{isDraft ? "Draft" : "Active"}</Badge>
          </DialogTitle>
          <DialogDescription className="font-mono text-xs">{trade.option_symbol}</DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-1">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Stop-Loss (futures pts)</Label>
              <input
                type="number"
                step="0.5"
                className={inputCls}
                value={slPoints}
                onChange={(e) => setSlPoints(e.target.value)}
              />
            </div>
            {isDraft && (
              <div className="space-y-1.5">
                <Label className="text-xs">Lots</Label>
                <div className="flex items-center gap-1.5">
                  <button type="button" className="rounded-lg border p-1.5" onClick={() => setLots((l) => Math.max(1, l - 1))}>
                    <Minus className="h-3.5 w-3.5" />
                  </button>
                  <input
                    type="number"
                    min={1}
                    value={lots}
                    onChange={(e) => setLots(Math.max(1, parseInt(e.target.value, 10) || 1))}
                    className="h-9 w-full rounded-lg border border-input bg-transparent px-2 text-center text-sm"
                  />
                  <button type="button" className="rounded-lg border p-1.5" onClick={() => setLots((l) => l + 1)}>
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Trailing mode</Label>
            <select className={inputCls} value={trailing} onChange={(e) => setTrailing(e.target.value as TrailingMode | "")}>
              <option value="">(keep current)</option>
              <option value="entry_after_t1">Break-even after T1</option>
              <option value="prev_target">Trail to previous target</option>
              <option value="off">Off</option>
            </select>
          </div>

          <div className="rounded-lg border p-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Pending targets (pts → % exit)</span>
              <div className="flex items-center gap-2">
                {editTargets && (
                  <button type="button" className="text-[11px] text-primary" onClick={() => setTargets((rows) => autoSplitTargets(rows))}>
                    Auto Split
                  </button>
                )}
                <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <input type="checkbox" checked={editTargets} onChange={(e) => setEditTargets(e.target.checked)} className="h-3.5 w-3.5" />
                  Edit
                </label>
              </div>
            </div>
            <div className="mt-2 space-y-1.5">
              {targets.map((t, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="w-8 text-muted-foreground">T{i + 1}</span>
                  <input
                    type="number"
                    disabled={!editTargets}
                    value={t.points}
                    onChange={(e) => setTargets((rows) => rows.map((r, idx) => (idx === i ? { ...r, points: Number(e.target.value) } : r)))}
                    className="h-7 w-20 rounded border border-input bg-transparent px-1.5 text-center disabled:opacity-60"
                  />
                  <span className="text-muted-foreground">pts</span>
                  <input
                    type="number"
                    disabled={!editTargets}
                    value={t.exit_pct}
                    onChange={(e) => setTargets((rows) => rows.map((r, idx) => (idx === i ? { ...r, exit_pct: Number(e.target.value) } : r)))}
                    className="h-7 w-16 rounded border border-input bg-transparent px-1.5 text-center disabled:opacity-60"
                  />
                  <span className="text-muted-foreground">% exit</span>
                </div>
              ))}
              {targets.length === 0 && <p className="text-[11px] text-muted-foreground">No pending targets to edit.</p>}
              {editTargets && (
                <button
                  type="button"
                  className="mt-1 flex items-center gap-1 text-[11px] text-primary"
                  onClick={() =>
                    setTargets((rows) => {
                      const lastPoints = [...rows].reverse().find((row) => row.points > 0)?.points ?? 0;
                      return autoSplitTargets([...rows, { points: lastPoints + 50, exit_pct: 0 }]);
                    })
                  }
                >
                  <Plus className="h-3 w-3" /> add target
                </button>
              )}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={save} disabled={mutation.isPending}>
            <Save className="mr-1 h-4 w-4" /> Save changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
