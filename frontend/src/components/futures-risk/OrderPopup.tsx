import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Minus, Plus, Settings, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";

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
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { useMarketData } from "@/hooks/useMarketData";
import {
  createDraft,
  getFrConfig,
  listExpiries,
  listStrikes,
  listSymbolMaps,
  listTargetTemplates,
  placeTrade,
} from "@/api/futuresRisk";
import type { OptionType, PlaceTradePayload, Side } from "@/types/futuresRisk";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPlaced?: () => void;
}

const QUICK_ORDER_SETTINGS_KEY = "openbull:futures-risk:quick-order-settings";

function formatStrikeForSymbol(strike: number): string {
  return Number.isInteger(strike) ? String(strike) : String(strike).replace(/\.0+$/, "").replace(".", "");
}

export function FuturesRiskOrderPopup({ open, onOpenChange, onPlaced }: Props) {
  const qc = useQueryClient();

  const mapsQuery = useQuery({ queryKey: ["fr-symbol-maps"], queryFn: listSymbolMaps, enabled: open });
  const configQuery = useQuery({ queryKey: ["fr-config"], queryFn: getFrConfig, enabled: open });
  const templatesQuery = useQuery({ queryKey: ["fr-target-templates"], queryFn: listTargetTemplates, enabled: open });

  const underlyings = useMemo(
    () => (mapsQuery.data ?? []).filter((m) => m.enabled),
    [mapsQuery.data],
  );

  const [underlying, setUnderlying] = useState("");
  const [expiry, setExpiry] = useState("");
  const [strike, setStrike] = useState<number | "">("");
  const [lots, setLots] = useState(1);
  const [slPoints, setSlPoints] = useState<string>("");
  const [targetTemplateId, setTargetTemplateId] = useState<number | null>(null);
  const [overrideTargets, setOverrideTargets] = useState(false);
  const [targetRows, setTargetRows] = useState<{ points: number; exit_pct: number }[]>([]);
  const [asDraft, setAsDraft] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [ceStrike, setCeStrike] = useState<number | "">("");
  const [peStrike, setPeStrike] = useState<number | "">("");
  const [settingsHydrated, setSettingsHydrated] = useState(false);
  const [hasSavedSettings, setHasSavedSettings] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(QUICK_ORDER_SETTINGS_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as Partial<{
          underlying: string;
          expiry: string;
          ceStrike: number;
          peStrike: number;
          lots: number;
          slPoints: string;
          targetTemplateId: number | null;
          overrideTargets: boolean;
          targetRows: { points: number; exit_pct: number }[];
          asDraft: boolean;
        }>;
        if (saved.underlying) setUnderlying(saved.underlying);
        if (saved.expiry) setExpiry(saved.expiry);
        if (Number(saved.ceStrike) > 0) setCeStrike(Number(saved.ceStrike));
        if (Number(saved.peStrike) > 0) setPeStrike(Number(saved.peStrike));
        if (Number(saved.lots) > 0) setLots(Number(saved.lots));
        if (saved.slPoints != null) setSlPoints(String(saved.slPoints));
        if ("targetTemplateId" in saved) setTargetTemplateId(saved.targetTemplateId ?? null);
        if (typeof saved.overrideTargets === "boolean") setOverrideTargets(saved.overrideTargets);
        if (Array.isArray(saved.targetRows)) setTargetRows(saved.targetRows);
        if (typeof saved.asDraft === "boolean") setAsDraft(saved.asDraft);
        setHasSavedSettings(true);
      }
    } catch {
      window.localStorage.removeItem(QUICK_ORDER_SETTINGS_KEY);
    } finally {
      setSettingsHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!settingsHydrated) return;
    if (!underlying && !expiry) return;
    window.localStorage.setItem(
      QUICK_ORDER_SETTINGS_KEY,
      JSON.stringify({
        underlying,
        expiry,
        ceStrike,
        peStrike,
        lots,
        slPoints,
        targetTemplateId,
        overrideTargets,
        targetRows,
        asDraft,
      }),
    );
  }, [asDraft, ceStrike, expiry, lots, overrideTargets, peStrike, settingsHydrated, slPoints, targetRows, targetTemplateId, underlying]);

  // Pre-fill defaults from admin config once loaded.
  useEffect(() => {
    if (configQuery.data && settingsHydrated && !hasSavedSettings) {
      const configuredLots = Number(configQuery.data.default_lots?.value);
      if (Number.isFinite(configuredLots) && configuredLots > 0) {
        setLots((prev) => (prev === 1 ? configuredLots : prev));
      }
      const configuredSl = configQuery.data.default_sl_points?.value;
      if (slPoints === "" && configuredSl != null) {
        setSlPoints(String(configuredSl));
      }
    }
  }, [configQuery.data, hasSavedSettings, settingsHydrated, slPoints]);

  const templates = useMemo(
    () => (templatesQuery.data ?? []).filter((t) => t.enabled),
    [templatesQuery.data],
  );
  const selectedTemplate = useMemo(
    () => templates.find((t) => t.id === targetTemplateId) ?? null,
    [templates, targetTemplateId],
  );

  useEffect(() => {
    if (templates.length === 0) return;
    if (targetTemplateId && templates.some((t) => t.id === targetTemplateId)) return;
    const next = templates.find((t) => t.is_default) ?? templates[0];
    setTargetTemplateId(next.id);
  }, [templates, targetTemplateId]);

  useEffect(() => {
    if (!selectedTemplate || overrideTargets) return;
    setTargetRows(
      selectedTemplate.targets.filter((t) => t.enabled).map((t) => ({ points: t.points, exit_pct: t.exit_pct })),
    );
  }, [overrideTargets, selectedTemplate]);

  // Default the underlying to the first available.
  useEffect(() => {
    if (!settingsHydrated) return;
    if (underlying || underlyings.length === 0) return;
    const preferredUnderlying = String(configQuery.data?.default_underlying?.value ?? "").toUpperCase();
    const preferred = underlyings.find((m) => m.underlying === preferredUnderlying);
    setUnderlying((preferred ?? underlyings[0]).underlying);
  }, [configQuery.data, settingsHydrated, underlyings, underlying]);

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
    refetchInterval: open && !!underlying && !!expiry ? 5000 : false,
  });

  // Default the strike to ATM when the strike list (re)loads.
  useEffect(() => {
    const d = strikesQuery.data;
    if (!d) return;
    const validStrikes = d.strikes.filter((s) => Number.isFinite(s) && s > 0);
    const currentStrike = strike === "" ? null : Number(strike);
    const hasCurrentStrike = currentStrike != null && validStrikes.includes(currentStrike);
    const atmStrike = d.atm && d.atm > 0 && validStrikes.includes(d.atm) ? d.atm : null;

    if (hasCurrentStrike) return;

    if (atmStrike) {
      setStrike(atmStrike);
      setCeStrike((prev) => (prev === "" || !validStrikes.includes(Number(prev)) ? atmStrike : prev));
      setPeStrike((prev) => (prev === "" || !validStrikes.includes(Number(prev)) ? atmStrike : prev));
    } else if (validStrikes.length) {
      const fallbackStrike = validStrikes[Math.floor(validStrikes.length / 2)];
      setStrike(fallbackStrike);
      setCeStrike((prev) => (prev === "" || !validStrikes.includes(Number(prev)) ? fallbackStrike : prev));
      setPeStrike((prev) => (prev === "" || !validStrikes.includes(Number(prev)) ? fallbackStrike : prev));
    } else {
      setStrike("");
      setCeStrike("");
      setPeStrike("");
    }
  }, [strikesQuery.data, strike]);

  const mutation = useMutation({
    mutationFn: (payload: PlaceTradePayload) => (asDraft ? createDraft(payload) : placeTrade(payload)),
    onSuccess: (trade) => {
      toast.success(
        asDraft
          ? `Draft saved - ${trade.side} ${trade.lots} lot ${trade.option_symbol}`
          : `${trade.side} ${trade.lots} lot ${trade.option_symbol} placed - entry futures ${trade.entry_futures_price}`,
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
    const selectedStrike = Number(optionType === "CE" ? ceStrike : peStrike);
    if (!underlying || !expiry || !Number.isFinite(selectedStrike) || selectedStrike <= 0) {
      toast.error("Configure instrument, expiry and strike first");
      return;
    }
    const payload: PlaceTradePayload = {
      underlying,
      underlying_exchange: underlyingExchange,
      expiry,
      option_type: optionType,
      side,
      lots,
      strike: selectedStrike,
      sl_points: slPoints === "" ? null : Number(slPoints),
      targets: overrideTargets ? targetRows.filter((t) => t.points > 0) : null,
      target_template_id: overrideTargets ? null : targetTemplateId,
    };
    mutation.mutate(payload);
  };

  const busy = mutation.isPending;
  const pendingLabel = asDraft ? "Saving..." : "Placing...";
  const expiryList = expiriesQuery.data ?? [];
  const strikeList = strikesQuery.data?.strikes ?? [];
  const atm = strikesQuery.data?.atm;
  const optionExchange = strikesQuery.data?.options_exchange ?? "NFO";
  const ceStrikeLabel = ceStrike === "" ? "--" : String(ceStrike);
  const peStrikeLabel = peStrike === "" ? "--" : String(peStrike);
  const ceSymbol = underlying && expiry && Number(ceStrike) > 0
    ? `${underlying}${expiry.toUpperCase()}${formatStrikeForSymbol(Number(ceStrike))}CE`
    : "";
  const peSymbol = underlying && expiry && Number(peStrike) > 0
    ? `${underlying}${expiry.toUpperCase()}${formatStrikeForSymbol(Number(peStrike))}PE`
    : "";
  const liveSymbols = useMemo(() => {
    const out: Array<{ symbol: string; exchange: string }> = [];
    if (ceSymbol) out.push({ symbol: ceSymbol, exchange: optionExchange });
    if (peSymbol && peSymbol !== ceSymbol) out.push({ symbol: peSymbol, exchange: optionExchange });
    return out;
  }, [ceSymbol, optionExchange, peSymbol]);
  const { data: tickMap } = useMarketData({
    symbols: liveSymbols,
    mode: "LTP",
    enabled: open && liveSymbols.length > 0,
  });
  const ceLtp = ceSymbol ? tickMap.get(`${optionExchange}:${ceSymbol}`)?.data.ltp : undefined;
  const peLtp = peSymbol ? tickMap.get(`${optionExchange}:${peSymbol}`)?.data.ltp : undefined;
  const targetSummary =
    targetRows.length > 0
      ? targetRows.map((t, i) => `T${i + 1} ${t.points} / ${t.exit_pct}%`).join(" | ")
      : "No targets configured";
  const canSubmitCe = !!underlying && !!expiry && Number(ceStrike) > 0 && !busy;
  const canSubmitPe = !!underlying && !!expiry && Number(peStrike) > 0 && !busy;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="gap-2.5 overflow-hidden p-3 sm:max-w-[330px]">
          <DialogHeader className="pr-16">
            <DialogTitle className="text-base font-semibold tracking-tight">Quick Order</DialogTitle>
          </DialogHeader>
          <button
            type="button"
            className="absolute right-11 top-2 inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={() => setSettingsOpen(true)}
            aria-label="Quick order settings"
            title="Settings"
          >
            <Settings className="h-4 w-4" />
          </button>

          <div className="grid grid-cols-2 gap-2">
            <QuickActionButton
              disabled={!canSubmitCe}
              busy={busy}
              pendingLabel={pendingLabel}
              tone="buy"
              label="Buy CE"
              strike={`${ceStrikeLabel} CE`}
              ltp={ceLtp}
              Icon={TrendingUp}
              onClick={() => submit("BUY", "CE")}
            />
            <QuickActionButton
              disabled={!canSubmitCe}
              busy={busy}
              pendingLabel={pendingLabel}
              tone="sell"
              label="Sell CE"
              strike={`${ceStrikeLabel} CE`}
              ltp={ceLtp}
              Icon={TrendingDown}
              onClick={() => submit("SELL", "CE")}
            />
            <QuickActionButton
              disabled={!canSubmitPe}
              busy={busy}
              pendingLabel={pendingLabel}
              tone="buy"
              label="Buy PE"
              strike={`${peStrikeLabel} PE`}
              ltp={peLtp}
              Icon={TrendingUp}
              onClick={() => submit("BUY", "PE")}
            />
            <QuickActionButton
              disabled={!canSubmitPe}
              busy={busy}
              pendingLabel={pendingLabel}
              tone="sell"
              label="Sell PE"
              strike={`${peStrikeLabel} PE`}
              ltp={peLtp}
              Icon={TrendingDown}
              onClick={() => submit("SELL", "PE")}
            />
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="max-h-[92vh] gap-0 overflow-hidden p-0 sm:max-w-[600px]">
          <div className="scrollbar-hidden max-h-[92vh] space-y-4 overflow-y-auto overscroll-contain p-4 sm:p-5">
            <DialogHeader className="space-y-1">
              <div className="flex items-center gap-2 pr-8">
                <button
                  type="button"
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                  onClick={() => setSettingsOpen(false)}
                  aria-label="Back to quick order"
                  title="Back"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                <DialogTitle className="text-base font-semibold tracking-tight">Quick Order Settings</DialogTitle>
              </div>
              <DialogDescription className="text-[11px] leading-tight">
                Changes auto-save and update the compact quick order buttons.
              </DialogDescription>
            </DialogHeader>

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
                <Field label={atm ? `CE Strike (ATM ${atm})` : "CE Strike"}>
                  <Select
                    value={ceStrike === "" ? "" : String(ceStrike)}
                    onValueChange={(v) => setCeStrike(v === "" ? "" : Number(v))}
                    disabled={strikeList.length === 0}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={strikesQuery.isLoading ? "Loading..." : "Select"} />
                    </SelectTrigger>
                    <SelectContent>
                      {strikeList.map((s) => (
                        <SelectItem key={s} value={String(s)}>
                          {s}
                          {atm === s ? " - ATM" : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label={atm ? `PE Strike (ATM ${atm})` : "PE Strike"}>
                  <Select
                    value={peStrike === "" ? "" : String(peStrike)}
                    onValueChange={(v) => setPeStrike(v === "" ? "" : Number(v))}
                    disabled={strikeList.length === 0}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={strikesQuery.isLoading ? "Loading..." : "Select"} />
                    </SelectTrigger>
                    <SelectContent>
                      {strikeList.map((s) => (
                        <SelectItem key={s} value={String(s)}>
                          {s}
                          {atm === s ? " - ATM" : ""}
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
              <Field label="Target Template">
                <Select
                  value={targetTemplateId == null ? "" : String(targetTemplateId)}
                  onValueChange={(v) => setTargetTemplateId(v ? Number(v) : null)}
                  disabled={templates.length === 0 || overrideTargets}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={templatesQuery.isLoading ? "Loading..." : "Select"} />
                  </SelectTrigger>
                  <SelectContent>
                    {templates.map((t) => (
                      <SelectItem key={t.id} value={String(t.id)}>
                        {t.name}{t.is_default ? " - default" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
                    {selectedTemplate && !overrideTargets ? `${selectedTemplate.name}: ${targetSummary}` : targetSummary}
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
              <p className="text-[11px] text-muted-foreground">No targets configured - add a target template in the admin panel.</p>
            ) : null}
          </div>
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
}

function QuickActionButton({
  disabled,
  busy,
  pendingLabel,
  tone,
  onClick,
  Icon,
  label,
  strike,
  ltp,
}: {
  disabled: boolean;
  busy: boolean;
  pendingLabel: string;
  tone: "buy" | "sell";
  onClick: () => void;
  Icon: typeof TrendingUp;
  label: string;
  strike: string;
  ltp?: number;
}) {
  return (
    <Button
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "h-12 flex-col items-center justify-center gap-0.5 rounded-full px-3 text-white shadow-md transition duration-150 hover:scale-[1.02] active:scale-[0.98] disabled:scale-100 disabled:opacity-50",
        tone === "buy"
          ? "bg-emerald-700 hover:bg-emerald-600"
          : "bg-rose-700 hover:bg-rose-600",
      )}
    >
      {busy ? pendingLabel : (
        <>
          <span className="flex items-center gap-1.5 text-[13px] font-bold leading-none">
            <Icon className="h-3.5 w-3.5 shrink-0" />
            {label}
          </span>
          <span className="text-[11px] font-semibold leading-none opacity-90">{strike}</span>
          <span className="text-[10px] font-semibold leading-none opacity-80">
            LTP {ltp === undefined ? "--" : ltp.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
          </span>
        </>
      )}
    </Button>
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
