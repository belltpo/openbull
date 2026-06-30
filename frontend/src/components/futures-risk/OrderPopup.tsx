import { useEffect, useMemo, useState, type ReactNode } from "react";
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
  createDraft,
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
  "h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 dark:[color-scheme:dark]";

const numCls =
  "rounded border border-input bg-background text-center text-foreground outline-none focus-visible:border-ring disabled:opacity-60 dark:[color-scheme:dark]";

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
  const [asDraft, setAsDraft] = useState(false);

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
    mutationFn: (payload: PlaceTradePayload) => (asDraft ? createDraft(payload) : placeTrade(payload)),
    onSuccess: (trade) => {
      toast.success(
        asDraft
          ? `Draft saved — ${trade.side} ${trade.lots} lot ${trade.option_symbol}`
          : `${trade.side} ${trade.lots} lot ${trade.option_symbol} placed — entry futures ${trade.entry_futures_price}`,
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

  const pendingLabel = asDraft ? "Saving…" : "Placing…";

  const OrderButton = ({
    side,
    optionType,
    label,
    Icon,
    className,
  }: {
    side: Side;
    optionType: OptionType;
    label: string;
    Icon: typeof TrendingUp;
    className: string;
  }) => (
    <Button disabled={busy} onClick={() => submit(side, optionType)} className={cn("h-10 justify-center", className)}>
      {busy ? (
        pendingLabel
      ) : (
        <>
          <Icon className="mr-1 h-4 w-4" /> {label}
        </>
      )}
    </Button>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 p-0 sm:max-w-[560px]">
        {/* Header */}
        <DialogHeader className="space-y-0 border-b px-4 py-3">
          <DialogTitle className="flex items-center justify-between gap-2 text-base">
            <span>Quick Options Order</span>
            <Badge variant={mode === "sandbox" ? "secondary" : "outline"}>
              {mode === "sandbox" ? "Sandbox" : "Live"}
            </Badge>
          </DialogTitle>
          <DialogDescription className="text-[11px] leading-tight">
            Targets &amp; stop-loss track the underlying futures price.
          </DialogDescription>
        </DialogHeader>

        {/* Contract */}
        <section className="space-y-2.5 px-4 py-3">
          <SectionLabel>Contract</SectionLabel>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <Field label="Instrument">
              <select className={inputCls} value={underlying} onChange={(e) => setUnderlying(e.target.value)}>
                {underlyings.length === 0 && <option value="">No mappings — add in admin</option>}
                {underlyings.map((m) => (
                  <option key={m.underlying} value={m.underlying}>
                    {m.underlying}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Expiry">
              <select className={inputCls} value={expiry} onChange={(e) => setExpiry(e.target.value)}>
                {(expiriesQuery.data ?? []).map((e) => (
                  <option key={e.value} value={e.value}>
                    {e.display}
                  </option>
                ))}
                {expiriesQuery.isLoading && <option>Loading…</option>}
              </select>
            </Field>
            <Field
              label={
                strikesQuery.data?.atm ? (
                  <>
                    Strike <span className="text-muted-foreground">(ATM {strikesQuery.data.atm})</span>
                  </>
                ) : (
                  "Strike"
                )
              }
            >
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
            </Field>
            <Field label="Lots">
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-input bg-background text-foreground"
                  onClick={() => setLots((l) => Math.max(1, l - 1))}
                >
                  <Minus className="h-3.5 w-3.5" />
                </button>
                <input
                  type="number"
                  min={1}
                  value={lots}
                  onChange={(e) => setLots(Math.max(1, parseInt(e.target.value, 10) || 1))}
                  className="h-9 w-full rounded-lg border border-input bg-background px-2 text-center text-sm text-foreground outline-none dark:[color-scheme:dark]"
                />
                <button
                  type="button"
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-input bg-background text-foreground"
                  onClick={() => setLots((l) => l + 1)}
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </div>
            </Field>
          </div>
        </section>

        {/* Risk */}
        <section className="space-y-2.5 border-t px-4 py-3">
          <SectionLabel>Risk</SectionLabel>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <Field label="Stop-loss (pts)">
              <Input
                type="number"
                step="0.5"
                value={slPoints}
                onChange={(e) => setSlPoints(e.target.value)}
                className="h-9"
              />
            </Field>
          </div>

          <div className="flex items-center justify-between pt-0.5">
            <span className="text-xs font-medium">Targets (futures points → % exit)</span>
            <label className="flex shrink-0 items-center gap-1.5 text-[11px] text-muted-foreground">
              <input
                type="checkbox"
                checked={overrideTargets}
                onChange={(e) => setOverrideTargets(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              Override
            </label>
          </div>
          {targetRows.length > 0 && (
            <>
              <div className="grid grid-cols-[2rem_1fr_1fr] gap-2 px-1 text-[11px] text-muted-foreground">
                <span />
                <span>Points</span>
                <span>% Exit</span>
              </div>
              <div className="space-y-1.5">
                {targetRows.map((t, i) => (
                  <div key={i} className="grid grid-cols-[2rem_1fr_1fr] items-center gap-2 text-xs">
                    <span className="text-muted-foreground">T{i + 1}</span>
                    <input
                      type="number"
                      disabled={!overrideTargets}
                      value={t.points}
                      onChange={(e) =>
                        setTargetRows((rows) =>
                          rows.map((r, idx) => (idx === i ? { ...r, points: Number(e.target.value) } : r)),
                        )
                      }
                      className={cn("h-7 w-full px-1.5 text-xs", numCls)}
                    />
                    <input
                      type="number"
                      disabled={!overrideTargets}
                      value={t.exit_pct}
                      onChange={(e) =>
                        setTargetRows((rows) =>
                          rows.map((r, idx) => (idx === i ? { ...r, exit_pct: Number(e.target.value) } : r)),
                        )
                      }
                      className={cn("h-7 w-full px-1.5 text-xs", numCls)}
                    />
                  </div>
                ))}
              </div>
            </>
          )}
          {targetRows.length === 0 && (
            <p className="text-[11px] text-muted-foreground">No targets configured — add them in the admin panel.</p>
          )}
        </section>

        {/* Draft toggle */}
        <section className="border-t px-4 py-2.5">
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={asDraft} onChange={(e) => setAsDraft(e.target.checked)} className="h-3.5 w-3.5" />
            <span>
              <span className="font-medium">Save as draft</span>{" "}
              <span className="text-muted-foreground">— editable, place later (no order sent now)</span>
            </span>
          </label>
        </section>

        {/* Summary + actions */}
        <DialogFooter className="block border-t px-4 py-3">
          <div className="mb-2.5 grid grid-cols-2 gap-x-3 gap-y-1 rounded-md bg-muted/50 px-2.5 py-1.5 text-[11px] sm:grid-cols-3">
            <SummaryItem label="Instr" value={underlying || "—"} />
            <SummaryItem label="Exp" value={expiry || "—"} />
            <SummaryItem label="Strike" value={strike === "" ? "—" : String(strike)} />
            <SummaryItem label="Lots" value={String(lots)} />
            <SummaryItem label="Mode" value={mode === "sandbox" ? "Sandbox" : "Live"} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <OrderButton side="BUY" optionType="CE" label="Buy CE" Icon={TrendingUp} className="bg-green-600 text-white hover:bg-green-700" />
            <OrderButton side="SELL" optionType="CE" label="Sell CE" Icon={TrendingDown} className="bg-red-600 text-white hover:bg-red-700" />
            <OrderButton side="BUY" optionType="PE" label="Buy PE" Icon={TrendingDown} className="bg-green-600 text-white hover:bg-green-700" />
            <OrderButton side="SELL" optionType="PE" label="Sell PE" Icon={TrendingUp} className="bg-red-600 text-white hover:bg-red-700" />
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{children}</h3>;
}

function Field({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-muted-foreground">{label}:</span>
      <span className="font-medium">{value}</span>
    </span>
  );
}
