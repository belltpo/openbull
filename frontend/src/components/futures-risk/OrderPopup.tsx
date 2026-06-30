import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Minus, Plus, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

export function FuturesRiskOrderPopup({ open, onOpenChange, onPlaced }: Props) {
  const { mode } = useTradingMode();
  const qc = useQueryClient();
  const isSandbox = mode === "sandbox";

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
  const pendingLabel = asDraft ? "Saving..." : "Placing...";
  const expiryList = expiriesQuery.data ?? [];
  const strikeList = strikesQuery.data?.strikes ?? [];
  const atm = strikesQuery.data?.atm;
  const activeTargets = targetRows.filter((t) => t.points > 0);
  const targetSummary =
    activeTargets.length > 0
      ? activeTargets.map((t) => `${t.points} / ${t.exit_pct}%`).join(" | ")
      : "No targets";
  const canSubmit = !!underlying && !!expiry && strike !== "" && !busy;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] gap-0 overflow-hidden p-0 sm:max-w-[600px]">
        <div className="scrollbar-hidden max-h-[92vh] space-y-4 overflow-y-auto overscroll-contain p-4 sm:p-5">
          {/* Header */}
          <DialogHeader className="space-y-1">
            <DialogTitle className="flex items-center justify-between gap-2 text-base">
              <span className="font-semibold tracking-tight">Quick Options Order</span>
              <Badge
                className={cn(
                  "border-transparent px-2 py-0.5 text-[11px] font-medium",
                  isSandbox
                    ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                    : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
                )}
              >
                {isSandbox ? "Sandbox" : "Live"}
              </Badge>
            </DialogTitle>
            <DialogDescription className="text-[11px] leading-tight">
              Stop-loss &amp; targets track the underlying futures price.
            </DialogDescription>
          </DialogHeader>

          {/* Contract */}
          <div className="space-y-2.5">
            <SectionLabel>Contract</SectionLabel>
            <div className="grid grid-cols-1 gap-2.5 min-[480px]:grid-cols-2 min-[600px]:grid-cols-4">
              <Field label="Instrument">
                <Select value={underlying} onValueChange={setUnderlying}>
                  <SelectTrigger>
                    <SelectValue placeholder={underlyings.length === 0 ? "No mappings" : "Select"} />
                  </SelectTrigger>
                  <SelectContent>
                    {underlyings.map((m) => (
                      <SelectItem key={m.underlying} value={m.underlying}>
                        {m.underlying}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Expiry">
                <Select value={expiry} onValueChange={setExpiry} disabled={expiryList.length === 0}>
                  <SelectTrigger>
                    <SelectValue placeholder={expiriesQuery.isLoading ? "Loading..." : "Select"} />
                  </SelectTrigger>
                  <SelectContent>
                    {expiryList.map((e) => (
                      <SelectItem key={e.value} value={e.value}>
                        {e.display}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label={atm ? `Strike (ATM ${atm})` : "Strike"}>
                <Select
                  value={strike === "" ? "" : String(strike)}
                  onValueChange={(v) => setStrike(v === "" ? "" : Number(v))}
                  disabled={strikeList.length === 0}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={strikesQuery.isLoading ? "Loading..." : "Select"} />
                  </SelectTrigger>
                  <SelectContent>
                    {strikeList.map((s) => (
                      <SelectItem key={s} value={String(s)}>
                        {s}
                        {atm === s ? "  • ATM" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Lots">
                <div className="flex h-9 items-stretch overflow-hidden rounded-md border border-input">
                  <button
                    type="button"
                    className="flex w-9 shrink-0 items-center justify-center border-r border-input bg-background text-muted-foreground hover:bg-accent"
                    onClick={() => setLots((l) => Math.max(1, l - 1))}
                  >
                    <Minus className="h-3.5 w-3.5" />
                  </button>
                  <input
                    type="number"
                    min={1}
                    value={lots}
                    onChange={(e) => setLots(Math.max(1, parseInt(e.target.value, 10) || 1))}
                    className="min-w-0 flex-1 bg-background px-1 text-center text-sm outline-none [appearance:textfield] dark:[color-scheme:dark] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <button
                    type="button"
                    className="flex w-9 shrink-0 items-center justify-center border-l border-input bg-background text-muted-foreground hover:bg-accent"
                    onClick={() => setLots((l) => l + 1)}
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
              </Field>
            </div>
          </div>

          {/* Risk */}
          <div className="space-y-2.5">
            <SectionLabel>Risk Controls</SectionLabel>
            <div className="grid grid-cols-1 gap-2.5 min-[440px]:grid-cols-2">
              <Field label="Stop-loss (pts)">
                <Input
                  type="number"
                  step="0.5"
                  value={slPoints}
                  onChange={(e) => setSlPoints(e.target.value)}
                  className="h-9 dark:[color-scheme:dark]"
                />
              </Field>
              <div className="flex items-end">
                <label className="flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-2.5 text-[11px] text-muted-foreground">
                  <span className="min-w-0 truncate">Draft only</span>
                  <Switch checked={asDraft} onCheckedChange={setAsDraft} />
                </label>
              </div>
            </div>

            <div className="rounded-lg border border-border/70 bg-muted/25 px-3 py-2">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex shrink-0 items-center rounded-md border border-border/70 bg-card px-2 py-1 text-[11px] font-semibold text-foreground">
                      Targets
                    </span>
                    <span className="text-[10px] text-muted-foreground">points / % exit</span>
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                    {targetSummary}
                  </p>
                </div>
                <label className="flex shrink-0 items-center gap-1.5 text-[11px] text-muted-foreground">
                  Override
                  <Switch checked={overrideTargets} onCheckedChange={setOverrideTargets} />
                </label>
              </div>
            </div>

            {overrideTargets && targetRows.length > 0 ? (
              <div className="space-y-1.5">
                <div className="grid grid-cols-[1.25rem_1fr_1fr] gap-2 px-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                  <span />
                  <span>Points</span>
                  <span>% Exit</span>
                </div>
                {targetRows.map((t, i) => (
                  <div key={i} className="grid grid-cols-[1.25rem_minmax(0,1fr)_minmax(0,1fr)] items-center gap-2">
                    <span className="text-[11px] font-medium text-muted-foreground">T{i + 1}</span>
                    <input
                      type="number"
                      value={t.points}
                      onChange={(e) =>
                        setTargetRows((rows) =>
                          rows.map((r, idx) => (idx === i ? { ...r, points: Number(e.target.value) } : r)),
                        )
                      }
                      className="h-8 w-full min-w-0 rounded-md border border-input bg-background px-2 text-center text-xs text-foreground outline-none focus-visible:border-ring dark:[color-scheme:dark]"
                    />
                    <input
                      type="number"
                      value={t.exit_pct}
                      onChange={(e) =>
                        setTargetRows((rows) =>
                          rows.map((r, idx) => (idx === i ? { ...r, exit_pct: Number(e.target.value) } : r)),
                        )
                      }
                      className="h-8 w-full min-w-0 rounded-md border border-input bg-background px-2 text-center text-xs text-foreground outline-none focus-visible:border-ring dark:[color-scheme:dark]"
                    />
                  </div>
                ))}
              </div>
            ) : targetRows.length === 0 ? (
              <p className="text-[11px] text-muted-foreground">No targets configured - add them in the admin panel.</p>
            ) : null}
          </div>

          {/* Preview */}
          <div className="grid grid-cols-2 gap-x-2 gap-y-1.5 rounded-lg border border-border/70 bg-muted/35 px-3 py-2 text-[11px] min-[520px]:grid-cols-6">
            <SummaryItem label="Instr" value={underlying || "-"} />
            <SummaryItem label="Exp" value={expiry || "-"} />
            <SummaryItem label="Strike" value={strike === "" ? "-" : String(strike)} />
            <SummaryItem label="Lots" value={String(lots)} />
            <SummaryItem label="SL" value={slPoints === "" ? "-" : slPoints} />
            <SummaryItem label="Mode" value={isSandbox ? "Sandbox" : "Live"} />
          </div>

          {/* Actions */}
          <div className="grid grid-cols-1 gap-3 min-[540px]:grid-cols-2">
            <DirectionGroup title="Bullish" subtitle="Targets above futures" tone="bullish">
              <OrderButton
                disabled={!canSubmit}
                busy={busy}
                pendingLabel={pendingLabel}
                onClick={() => submit("BUY", "CE")}
                className="bg-emerald-600 text-white hover:bg-emerald-700"
                Icon={TrendingUp}
                label="Buy CE"
              />
              <OrderButton
                disabled={!canSubmit}
                busy={busy}
                pendingLabel={pendingLabel}
                onClick={() => submit("SELL", "PE")}
                className="bg-emerald-700 text-white hover:bg-emerald-800"
                Icon={TrendingUp}
                label="Sell PE"
              />
            </DirectionGroup>

            <DirectionGroup title="Bearish" subtitle="Targets below futures" tone="bearish">
              <OrderButton
                disabled={!canSubmit}
                busy={busy}
                pendingLabel={pendingLabel}
                onClick={() => submit("BUY", "PE")}
                className="bg-rose-600 text-white hover:bg-rose-700"
                Icon={TrendingDown}
                label="Buy PE"
              />
              <OrderButton
                disabled={!canSubmit}
                busy={busy}
                pendingLabel={pendingLabel}
                onClick={() => submit("SELL", "CE")}
                className="bg-rose-700 text-white hover:bg-rose-800"
                Icon={TrendingDown}
                label="Sell CE"
              />
            </DirectionGroup>
          </div>

          {!canSubmit && !busy ? (
            <p className="text-center text-[11px] text-muted-foreground">
              Select instrument, expiry, and strike to enable order actions.
            </p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function OrderButton({
  disabled,
  busy,
  pendingLabel,
  onClick,
  className,
  Icon,
  label,
}: {
  disabled: boolean;
  busy: boolean;
  pendingLabel: string;
  onClick: () => void;
  className: string;
  Icon: typeof TrendingUp;
  label: string;
}) {
  return (
    <Button
      disabled={disabled}
      onClick={onClick}
      className={cn("h-10 justify-center text-sm font-semibold", className)}
    >
      {busy ? pendingLabel : (
        <>
          <Icon className="mr-1.5 h-4 w-4" /> {label}
        </>
      )}
    </Button>
  );
}

function DirectionGroup({
  title,
  subtitle,
  tone,
  children,
}: {
  title: string;
  subtitle: string;
  tone: "bullish" | "bearish";
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-border/70 bg-card px-3 py-2.5">
      <div className="mb-2 min-w-0">
        <p
          className={cn(
            "text-xs font-semibold",
            tone === "bullish"
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-rose-600 dark:text-rose-400",
          )}
        >
          {title}
        </p>
        <p className="truncate text-[10px] text-muted-foreground">{subtitle}</p>
      </div>
      <div className="grid grid-cols-2 gap-2">{children}</div>
    </section>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-1.5">
      <ShieldCheck className="h-3.5 w-3.5 text-muted-foreground" />
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{children}</h3>
    </div>
  );
}

function Field({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-[11px] font-medium text-muted-foreground">{label}</Label>
      {children}
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex items-center gap-1 overflow-hidden">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="truncate font-medium">{value}</span>
    </span>
  );
}
