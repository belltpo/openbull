import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Minus, Plus, Settings, ShieldCheck, TrendingDown, TrendingUp, X } from "lucide-react";

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
  resolveFutures,
} from "@/api/futuresRisk";
import type { OptionType, PlaceTradePayload, Side } from "@/types/futuresRisk";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPlaced?: () => void;
}

const QUICK_ORDER_SETTINGS_KEY = "openbull:futures-risk:quick-order-settings";
const CONTRACT_ORDER_TEMPLATES_KEY = "contract_order_templates";

type ContractOrderDefaults = {
  lots?: string;
  sl_points?: string;
  product?: string;
};

type TargetOverrideRow = { points: number; exit_pct: number };

function splitExitPercent(count: number): number[] {
  if (count <= 0) return [];
  const base = Math.floor(10000 / count) / 100;
  const values = Array.from({ length: count }, () => base);
  values[count - 1] = Number((100 - values.slice(0, -1).reduce((sum, value) => sum + value, 0)).toFixed(2));
  return values;
}

function autoSplitTargets(rows: TargetOverrideRow[]): TargetOverrideRow[] {
  const split = splitExitPercent(rows.filter((row) => row.points > 0).length);
  let splitIndex = 0;
  return rows.map((row) => {
    if (row.points <= 0) return { ...row, exit_pct: 0 };
    return { ...row, exit_pct: split[splitIndex++] ?? 0 };
  });
}

function normalizeTargetRows(rows: TargetOverrideRow[]): TargetOverrideRow[] {
  const active = rows.filter((row) => row.points > 0);
  const total = Number(active.reduce((sum, row) => sum + Number(row.exit_pct || 0), 0).toFixed(2));
  return active.length > 0 && Math.abs(total - 100) > 0.01 ? autoSplitTargets(rows) : rows;
}

function formatStrikeForSymbol(strike: number): string {
  return Number.isInteger(strike) ? String(strike) : String(strike).replace(/\.0+$/, "").replace(".", "");
}

function DragGrip() {
  return (
    <span
      className="inline-flex h-5 w-9 items-center justify-center rounded-full border border-border/70 bg-muted/55 text-muted-foreground shadow-sm"
      aria-hidden="true"
    >
      <span className="grid grid-cols-3 gap-0.5">
        {Array.from({ length: 6 }).map((_, i) => (
          <span key={i} className="h-1 w-1 rounded-full bg-current opacity-75" />
        ))}
      </span>
    </span>
  );
}

function parseContractOrderDefaults(raw: string | undefined): Record<string, ContractOrderDefaults> {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return parsed as Record<string, ContractOrderDefaults>;
  } catch {
    return {};
  }
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
  const [targetRows, setTargetRows] = useState<TargetOverrideRow[]>([]);
  const [asDraft, setAsDraft] = useState(false);
  const [product, setProduct] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [ceStrike, setCeStrike] = useState<number | "">("");
  const [peStrike, setPeStrike] = useState<number | "">("");
  const [settingsHydrated, setSettingsHydrated] = useState(false);
  const [hasSavedSettings, setHasSavedSettings] = useState(false);
  const [quickOrderPosition, setQuickOrderPosition] = useState<{ x: number; y: number } | null>(null);
  const [settingsPosition, setSettingsPosition] = useState<{ x: number; y: number } | null>(null);
  const [draggingPanel, setDraggingPanel] = useState<"quick" | "settings" | null>(null);
  const dragOffsetRef = useRef({ x: 0, y: 0 });

  const clearContractSelection = (clearExpiry = true) => {
    if (clearExpiry) setExpiry("");
    setStrike("");
    setCeStrike("");
    setPeStrike("");
  };

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
          product: string;
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
        if (saved.product) setProduct(saved.product);
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
        product,
      }),
    );
  }, [asDraft, ceStrike, expiry, lots, overrideTargets, peStrike, product, settingsHydrated, slPoints, targetRows, targetTemplateId, underlying]);

  const closeQuickOrder = () => {
    setSettingsOpen(false);
    onOpenChange(false);
  };

  useEffect(() => {
    if (!draggingPanel) return;

    const move = (event: PointerEvent) => {
      const width = draggingPanel === "settings" ? Math.min(760, window.innerWidth - 16) : 354;
      const height = draggingPanel === "settings" ? Math.min(680, window.innerHeight - 16) : 300;
      const nextX = Math.max(8, Math.min(window.innerWidth - width - 8, event.clientX - dragOffsetRef.current.x));
      const nextY = Math.max(8, Math.min(window.innerHeight - height - 8, event.clientY - dragOffsetRef.current.y));
      if (draggingPanel === "settings") setSettingsPosition({ x: nextX, y: nextY });
      else setQuickOrderPosition({ x: nextX, y: nextY });
    };
    const stop = () => setDraggingPanel(null);

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, { once: true });
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
  }, [draggingPanel]);

  const startPanelDrag = (panel: "quick" | "settings", event: ReactPointerEvent<HTMLElement>) => {
    if (event.button !== 0) return;
    const popup = event.currentTarget.closest("[data-fr-floating-panel]") as HTMLElement | null;
    if (!popup) return;
    const rect = popup.getBoundingClientRect();
    dragOffsetRef.current = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
    if (panel === "settings") setSettingsPosition({ x: rect.left, y: rect.top });
    else setQuickOrderPosition({ x: rect.left, y: rect.top });
    setDraggingPanel(panel);
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const contractDefaults = useMemo(
    () => parseContractOrderDefaults(configQuery.data?.[CONTRACT_ORDER_TEMPLATES_KEY]?.value),
    [configQuery.data],
  );
  const selectedContractDefaults = underlying ? contractDefaults[underlying] : undefined;

  // Pre-fill the setup saved for the selected contract.
  useEffect(() => {
    if (!configQuery.data || !settingsHydrated || !underlying) return;

    const saved = selectedContractDefaults;
    if (saved) {
      const configuredLots = Number(saved.lots);
      if (Number.isFinite(configuredLots) && configuredLots > 0) setLots(configuredLots);
      if (saved.sl_points != null) setSlPoints(String(saved.sl_points));
      if (saved.product) setProduct(saved.product.toUpperCase());
      return;
    }

    if (!hasSavedSettings) {
      const configuredLots = Number(configQuery.data.default_lots?.value);
      if (Number.isFinite(configuredLots) && configuredLots > 0) setLots((prev) => (prev === 1 ? configuredLots : prev));
      const configuredSl = configQuery.data.default_sl_points?.value;
      if (slPoints === "" && configuredSl != null) setSlPoints(String(configuredSl));
      const configuredProduct = configQuery.data.default_product?.value;
      if (!product && configuredProduct) setProduct(String(configuredProduct).toUpperCase());
    }
  }, [configQuery.data, hasSavedSettings, product, selectedContractDefaults, settingsHydrated, slPoints, underlying]);

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
    const hasValidSelected = targetTemplateId && templates.some((t) => t.id === targetTemplateId);

    if (hasSavedSettings && hasValidSelected) return;
    if (hasValidSelected) return;

    const next = templates.find((t) => t.is_default) ?? templates[0];
    setTargetTemplateId(next.id);
  }, [hasSavedSettings, targetTemplateId, templates]);

  useEffect(() => {
    if (!selectedTemplate || overrideTargets) return;
    setTargetRows(normalizeTargetRows(selectedTemplate.targets.filter((t) => t.enabled).map((t) => ({ points: t.points, exit_pct: t.exit_pct }))));
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

  const futuresQuery = useQuery({
    queryKey: ["fr-resolve-futures", underlying],
    queryFn: () => resolveFutures(underlying),
    enabled: open && !!underlying,
  });

  const expiriesQuery = useQuery({
    queryKey: ["fr-expiries", underlying, underlyingExchange],
    queryFn: () => listExpiries(underlying, underlyingExchange),
    enabled: open && !!underlying,
  });

  useEffect(() => {
    if (!open || !underlying || expiriesQuery.isLoading || !expiriesQuery.data) return;
    const list = expiriesQuery.data;
    if (list.length === 0) {
      clearContractSelection();
      return;
    }
    if (!list.some((e) => e.value === expiry)) {
      setExpiry(list[0].value);
      clearContractSelection(false);
    }
  }, [expiriesQuery.data, expiriesQuery.isLoading, expiry, open, underlying]);

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
      if (trade.status === "error") {
        const message = trade.events?.find((event) => event.severity === "error")?.message ?? "Broker rejected the entry order";
        toast.error(message);
        qc.invalidateQueries({ queryKey: ["fr-trades"] });
        onPlaced?.();
        closeQuickOrder();
        return;
      }
      toast.success(
        asDraft
          ? `Draft saved - ${trade.side} ${trade.lots} lot ${trade.option_symbol}`
          : `${trade.side} ${trade.lots} lot ${trade.option_symbol} placed - entry futures ${trade.entry_futures_price}`,
      );
      qc.invalidateQueries({ queryKey: ["fr-trades"] });
      onPlaced?.();
      closeQuickOrder();
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
      product: product || undefined,
      strike: selectedStrike,
      sl_points: slPoints === "" ? null : Number(slPoints),
      targets: overrideTargets ? normalizeTargetRows(targetRows.filter((t) => t.points > 0)) : null,
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
  const futuresSymbol = futuresQuery.data?.symbol ?? selectedMap?.futures_symbol ?? "";
  const futuresExchange = futuresQuery.data?.exchange ?? selectedMap?.futures_exchange ?? "NFO";
  const ceSymbol = underlying && expiry && Number(ceStrike) > 0
    ? `${underlying}${expiry.toUpperCase()}${formatStrikeForSymbol(Number(ceStrike))}CE`
    : "";
  const peSymbol = underlying && expiry && Number(peStrike) > 0
    ? `${underlying}${expiry.toUpperCase()}${formatStrikeForSymbol(Number(peStrike))}PE`
    : "";
  const liveSymbols = useMemo(() => {
    const out: Array<{ symbol: string; exchange: string }> = [];
    if (futuresSymbol) out.push({ symbol: futuresSymbol, exchange: futuresExchange });
    if (ceSymbol) out.push({ symbol: ceSymbol, exchange: optionExchange });
    if (peSymbol && peSymbol !== ceSymbol) out.push({ symbol: peSymbol, exchange: optionExchange });
    return out;
  }, [ceSymbol, futuresExchange, futuresSymbol, optionExchange, peSymbol]);
  const { data: tickMap } = useMarketData({
    symbols: liveSymbols,
    mode: "LTP",
    enabled: open && liveSymbols.length > 0,
  });
  const futuresLtp = futuresSymbol ? tickMap.get(`${futuresExchange}:${futuresSymbol}`)?.data.ltp : undefined;
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
      {open && (
        <div
          data-fr-floating-panel
          role="dialog"
          aria-label="Quick Order"
          className={cn(
            "fixed left-1/2 top-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-[330px] -translate-x-1/2 -translate-y-1/2 gap-2.5 overflow-hidden rounded-xl bg-popover p-3 text-sm text-popover-foreground shadow-2xl ring-1 ring-foreground/10",
            quickOrderPosition && "left-0 top-0 translate-x-0 translate-y-0",
          )}
          style={quickOrderPosition ? { left: quickOrderPosition.x, top: quickOrderPosition.y, transform: "none" } : undefined}
        >
          <div
            className="absolute left-1/2 top-2 z-10 -translate-x-1/2 cursor-move select-none"
            onPointerDown={(event) => startPanelDrag("quick", event)}
            title="Drag"
            aria-label="Drag quick order"
          >
            <DragGrip />
          </div>
          <div className="cursor-move select-none pr-16" onPointerDown={(event) => startPanelDrag("quick", event)}>
            <h2 className="text-base font-semibold tracking-tight">Quick Order</h2>
          </div>
          <div className="rounded-xl border border-border/70 bg-muted/35 px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Futures Live</p>
                <p className="truncate font-mono text-[11px] text-muted-foreground">
                  {futuresSymbol || futuresQuery.isLoading ? futuresSymbol || "Resolving..." : "No futures mapping"}
                </p>
              </div>
              <p className="shrink-0 text-base font-bold tabular-nums">
                {futuresLtp === undefined ? "--" : futuresLtp.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="absolute right-11 top-2 inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={() => setSettingsOpen(true)}
            aria-label="Quick order settings"
            title="Settings"
          >
            <Settings className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="absolute right-2 top-2 inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={closeQuickOrder}
            aria-label="Close quick order"
            title="Close"
          >
            <X className="h-4 w-4" />
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
        </div>
      )}

      {settingsOpen && (
        <div
          data-fr-floating-panel
          role="dialog"
          aria-label="Quick Order Settings"
          className={cn(
            "fixed left-1/2 top-1/2 z-50 grid max-h-[92vh] w-[calc(100vw-2rem)] max-w-[600px] -translate-x-1/2 -translate-y-1/2 gap-0 overflow-hidden rounded-xl bg-popover p-0 text-sm text-popover-foreground shadow-2xl ring-1 ring-foreground/10",
            settingsPosition && "left-0 top-0 translate-x-0 translate-y-0",
          )}
          style={settingsPosition ? { left: settingsPosition.x, top: settingsPosition.y, transform: "none" } : undefined}
        >
          <div
            className="absolute left-1/2 top-2 z-10 -translate-x-1/2 cursor-move select-none"
            onPointerDown={(event) => startPanelDrag("settings", event)}
            title="Drag"
            aria-label="Drag quick order settings"
          >
            <DragGrip />
          </div>
          <div className="scrollbar-hidden max-h-[92vh] space-y-4 overflow-y-auto overscroll-contain p-4 sm:p-5">
            <div className="space-y-1">
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
                <div
                  className="min-w-0 flex-1 cursor-move select-none"
                  onPointerDown={(event) => startPanelDrag("settings", event)}
                >
                  <h2 className="truncate text-base font-semibold tracking-tight">Quick Order Settings</h2>
                </div>
              </div>
              <p className="text-[11px] leading-tight text-muted-foreground">
                Changes auto-save and update the compact quick order buttons.
              </p>
            </div>
            <button
              type="button"
              className="absolute right-2 top-2 inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={() => setSettingsOpen(false)}
              aria-label="Close quick order settings"
              title="Close"
            >
              <X className="h-4 w-4" />
            </button>

            <div className="space-y-2.5">
              <SectionLabel>Contract</SectionLabel>
              <div className="grid grid-cols-1 gap-2.5 min-[480px]:grid-cols-2 min-[600px]:grid-cols-4">
                <Field label="Instrument">
                  <Select
                    value={underlying}
                    onValueChange={(value) => {
                      setUnderlying(value);
                      clearContractSelection();
                    }}
                  >
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
                  <Select
                    value={expiry}
                    onValueChange={(value) => {
                      setExpiry(value);
                      clearContractSelection(false);
                    }}
                    disabled={expiryList.length === 0}
                  >
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
        </div>
      )}
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
