import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Minus, Plus, TrendingDown, TrendingUp } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useTradingMode } from "@/contexts/TradingModeContext";
import {
  getFrConfig,
  listExpiries,
  listStrikes,
  listSymbolMaps,
  listTargets,
  placeTrade,
} from "@/api/futuresRisk";
import type { OptionType, PlaceTradePayload, Side } from "@/types/futuresRisk";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPlaced?: () => void;
}

const inputCls =
  "h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3";

export function FuturesRiskOrderPopup({ open, onOpenChange, onPlaced }: Props) {
  const { mode } = useTradingMode();
  const qc = useQueryClient();

  const mapsQuery = useQuery({ queryKey: ["fr-symbol-maps"], queryFn: listSymbolMaps, enabled: open });
  const configQuery = useQuery({ queryKey: ["fr-config"], queryFn: getFrConfig, enabled: open });
  const targetsQuery = useQuery({ queryKey: ["fr-targets"], queryFn: listTargets, enabled: open });

  const underlyings = useMemo(
    () => (mapsQuery.data ?? []).filter((m) => m.enabled),
    [mapsQuery.data],
  );

  const [underlying, setUnderlying] = useState("");
  const [expiry, setExpiry] = useState("");
  const [strike, setStrike] = useState<number | "">("");
  const [lots, setLots] = useState(1);
  const [slPoints, setSlPoints] = useState<string>("");
  const [overrideTargets, setOverrideTargets] = useState(false);
  const [targetRows, setTargetRows] = useState<{ points: number; exit_pct: number }[]>([]);

  // Pre-fill defaults from admin config once loaded.
  useEffect(() => {
    if (configQuery.data) {
      setLots((prev) => (prev === 1 ? Number(configQuery.data.default_lots?.value ?? 1) || 1 : prev));
      setSlPoints((prev) => (prev === "" ? String(configQuery.data.default_sl_points?.value ?? "30") : prev));
    }
  }, [configQuery.data]);

  useEffect(() => {
    if (targetsQuery.data) {
      setTargetRows(
        targetsQuery.data.filter((t) => t.enabled).map((t) => ({ points: t.points, exit_pct: t.exit_pct })),
      );
    }
  }, [targetsQuery.data]);

  // Default the underlying to the first available.
  useEffect(() => {
    if (!underlying && underlyings.length > 0) setUnderlying(underlyings[0].underlying);
  }, [underlyings, underlying]);

  const selectedMap = underlyings.find((m) => m.underlying === underlying);
  const underlyingExchange = selectedMap?.underlying_exchange ?? "NSE_INDEX";

  const expiriesQuery = useQuery({
    queryKey: ["fr-expiries", underlying, underlyingExchange],
    queryFn: () => listExpiries(underlying, underlyingExchange),
    enabled: open && !!underlying,
  });

  useEffect(() => {
    const list = expiriesQuery.data ?? [];
    if (list.length > 0 && !list.some((e) => e.value === expiry)) setExpiry(list[0].value);
  }, [expiriesQuery.data, expiry]);

  const strikesQuery = useQuery({
    queryKey: ["fr-strikes", underlying, expiry, underlyingExchange],
    queryFn: () => listStrikes(underlying, expiry, "CE", underlyingExchange),
    enabled: open && !!underlying && !!expiry,
  });

  // Default the strike to ATM when the strike list (re)loads.
  useEffect(() => {
    const d = strikesQuery.data;
    if (!d) return;
    if (d.atm && (strike === "" || !d.strikes.includes(Number(strike)))) {
      setStrike(d.atm);
    } else if (!d.atm && d.strikes.length && strike === "") {
      setStrike(d.strikes[Math.floor(d.strikes.length / 2)]);
    }
  }, [strikesQuery.data, strike]);

  const mutation = useMutation({
    mutationFn: (payload: PlaceTradePayload) => placeTrade(payload),
    onSuccess: (trade) => {
      toast.success(
        `${trade.side} ${trade.lots} lot ${trade.option_symbol} placed — entry futures ${trade.entry_futures_price}`,
      );
      qc.invalidateQueries({ queryKey: ["fr-trades"] });
      onPlaced?.();
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const msg =
        // @ts-expect-error axios error shape
        err?.response?.data?.detail ?? (err instanceof Error ? err.message : "Order failed");
      toast.error(String(msg));
    },
  });

  const submit = (side: Side, optionType: OptionType) => {
    if (!underlying || !expiry || strike === "") {
      toast.error("Pick instrument, expiry and strike first");
      return;
    }
    const payload: PlaceTradePayload = {
      underlying,
      underlying_exchange: underlyingExchange,
      expiry,
      option_type: optionType,
      side,
      lots,
      strike: Number(strike),
      sl_points: slPoints === "" ? null : Number(slPoints),
      targets: overrideTargets ? targetRows.filter((t) => t.points > 0) : null,
    };
    mutation.mutate(payload);
  };

  const busy = mutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>Quick Options Order</span>
            <Badge variant={mode === "sandbox" ? "secondary" : "outline"}>
              {mode === "sandbox" ? "Sandbox" : "Live"}
            </Badge>
          </DialogTitle>
          <DialogDescription>
            Targets &amp; stop-loss are managed on the underlying futures price.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-1">
          {/* Instrument */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Instrument</Label>
              <select className={inputCls} value={underlying} onChange={(e) => setUnderlying(e.target.value)}>
                {underlyings.length === 0 && <option value="">No mappings — add in admin</option>}
                {underlyings.map((m) => (
                  <option key={m.underlying} value={m.underlying}>
                    {m.underlying}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Expiry</Label>
              <select className={inputCls} value={expiry} onChange={(e) => setExpiry(e.target.value)}>
                {(expiriesQuery.data ?? []).map((e) => (
                  <option key={e.value} value={e.value}>
                    {e.display}
                  </option>
                ))}
                {expiriesQuery.isLoading && <option>Loading…</option>}
              </select>
            </div>
          </div>

          {/* Strike + Lots */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">
                Strike{" "}
                {strikesQuery.data?.atm ? (
                  <span className="text-muted-foreground">(ATM {strikesQuery.data.atm})</span>
                ) : null}
              </Label>
              <select
                className={inputCls}
                value={strike}
                onChange={(e) => setStrike(e.target.value === "" ? "" : Number(e.target.value))}
              >
                {(strikesQuery.data?.strikes ?? []).map((s) => (
                  <option key={s} value={s}>
                    {s}
                    {strikesQuery.data?.atm === s ? "  • ATM" : ""}
                  </option>
                ))}
                {strikesQuery.isLoading && <option>Loading…</option>}
              </select>
            </div>
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
          </div>

          {/* SL override */}
          <div className="space-y-1.5">
            <Label className="text-xs">Stop-loss (futures points)</Label>
            <Input
              type="number"
              step="0.5"
              value={slPoints}
              onChange={(e) => setSlPoints(e.target.value)}
              className="h-9"
            />
          </div>

          {/* Targets */}
          <div className="rounded-lg border p-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Targets (futures points → % exit)</span>
              <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <input
                  type="checkbox"
                  checked={overrideTargets}
                  onChange={(e) => setOverrideTargets(e.target.checked)}
                  className="h-3.5 w-3.5"
                />
                Override
              </label>
            </div>
            <div className="mt-2 space-y-1.5">
              {targetRows.map((t, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="w-8 text-muted-foreground">T{i + 1}</span>
                  <input
                    type="number"
                    disabled={!overrideTargets}
                    value={t.points}
                    onChange={(e) =>
                      setTargetRows((rows) =>
                        rows.map((r, idx) => (idx === i ? { ...r, points: Number(e.target.value) } : r)),
                      )
                    }
                    className="h-7 w-20 rounded border border-input bg-transparent px-1.5 text-center disabled:opacity-60"
                  />
                  <span className="text-muted-foreground">pts</span>
                  <input
                    type="number"
                    disabled={!overrideTargets}
                    value={t.exit_pct}
                    onChange={(e) =>
                      setTargetRows((rows) =>
                        rows.map((r, idx) => (idx === i ? { ...r, exit_pct: Number(e.target.value) } : r)),
                      )
                    }
                    className="h-7 w-16 rounded border border-input bg-transparent px-1.5 text-center disabled:opacity-60"
                  />
                  <span className="text-muted-foreground">% exit</span>
                </div>
              ))}
              {targetRows.length === 0 && (
                <p className="text-[11px] text-muted-foreground">No targets configured — add them in the admin panel.</p>
              )}
            </div>
          </div>
        </div>

        <DialogFooter className="grid grid-cols-2 gap-2 sm:grid-cols-2">
          <Button
            disabled={busy}
            onClick={() => submit("BUY", "CE")}
            className="bg-green-600 text-white hover:bg-green-700"
          >
            <TrendingUp className="mr-1 h-4 w-4" /> Buy CE
          </Button>
          <Button
            disabled={busy}
            onClick={() => submit("SELL", "CE")}
            className="bg-red-600 text-white hover:bg-red-700"
          >
            <TrendingDown className="mr-1 h-4 w-4" /> Sell CE
          </Button>
          <Button
            disabled={busy}
            onClick={() => submit("BUY", "PE")}
            className="bg-green-700 text-white hover:bg-green-800"
          >
            <TrendingDown className="mr-1 h-4 w-4" /> Buy PE
          </Button>
          <Button
            disabled={busy}
            onClick={() => submit("SELL", "PE")}
            className={cn("bg-red-700 text-white hover:bg-red-800")}
          >
            <TrendingUp className="mr-1 h-4 w-4" /> Sell PE
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
