import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Plus, Save, Trash2 } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import {
  createSymbolMap,
  createTarget,
  deleteSymbolMap,
  deleteTarget,
  getFrConfig,
  listSymbolMaps,
  listTargets,
  setFrConfig,
  updateSymbolMap,
  updateTarget,
} from "@/api/futuresRisk";
import type { FrSymbolMap, FrTemplateTarget } from "@/types/futuresRisk";

const inputCls =
  "h-8 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25 dark:[color-scheme:dark]";
const rowCls = "rounded-md border border-border/70 bg-card px-2.5 py-2";

type SettingType = "bool" | "number" | "text" | "select";
const SETTINGS: { key: string; label: string; type: SettingType; options?: string[] }[] = [
  { key: "auto_exit_enabled", label: "Auto-exit enabled", type: "bool" },
  { key: "trailing_enabled", label: "Trailing stop-loss enabled", type: "bool" },
  { key: "trailing_mode", label: "Trailing mode", type: "select", options: ["entry_after_t1", "prev_target", "off"] },
  { key: "poll_interval_sec", label: "Poll interval (sec)", type: "number" },
];

const DEFAULT_ORDER_KEYS = ["default_underlying", "default_lots", "default_sl_points", "default_product"] as const;

function AdminPanel({
  title,
  description,
  action,
  className,
  contentClassName,
  children,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
  contentClassName?: string;
  children: ReactNode;
}) {
  return (
    <Card className={cn("overflow-hidden border-border/70 shadow-sm", className)}>
      <CardHeader className="flex flex-row items-start justify-between gap-3 border-b bg-muted/25 px-3 py-2.5 sm:px-4">
        <div className="min-w-0">
          <CardTitle className="text-sm font-semibold tracking-tight">{title}</CardTitle>
          <CardDescription className="mt-0.5 text-xs leading-tight">{description}</CardDescription>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </CardHeader>
      <CardContent className={cn("space-y-2.5 p-2.5 sm:p-3", contentClassName)}>{children}</CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Default quick-order setup
// ---------------------------------------------------------------------------

function DefaultOrderSetup() {
  const qc = useQueryClient();
  const cfgQuery = useQuery({ queryKey: ["fr-config"], queryFn: getFrConfig });
  const mapsQuery = useQuery({ queryKey: ["fr-symbol-maps"], queryFn: listSymbolMaps });
  const enabledMaps = (mapsQuery.data ?? []).filter((m) => m.enabled);
  const [local, setLocal] = useState<Record<(typeof DEFAULT_ORDER_KEYS)[number], string>>({
    default_underlying: "",
    default_lots: "1",
    default_sl_points: "30",
    default_product: "MIS",
  });

  useEffect(() => {
    if (!cfgQuery.data) return;
    const fallbackUnderlying = enabledMaps[0]?.underlying ?? "NIFTY";
    setLocal({
      default_underlying: String(cfgQuery.data.default_underlying?.value || fallbackUnderlying).toUpperCase(),
      default_lots: cfgQuery.data.default_lots?.value ?? "1",
      default_sl_points: cfgQuery.data.default_sl_points?.value ?? "30",
      default_product: cfgQuery.data.default_product?.value ?? "MIS",
    });
  }, [cfgQuery.data, enabledMaps]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const changed = DEFAULT_ORDER_KEYS.filter((key) => local[key] !== (cfgQuery.data?.[key]?.value ?? ""));
      await Promise.all(changed.map((key) => setFrConfig(key, local[key])));
      return changed.length;
    },
    onSuccess: (n) => {
      toast.success(n ? `Saved ${n} default(s)` : "No changes");
      qc.invalidateQueries({ queryKey: ["fr-config"] });
    },
    onError: (err: unknown) => {
      // @ts-expect-error axios error shape
      toast.error(String(err?.response?.data?.detail ?? "Save failed"));
    },
  });

  return (
    <AdminPanel
      title="Default Order Setup"
      description="Controls what opens by default in the quick options order card."
      className="h-full"
      action={
        <Button size="sm" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          <Save className="mr-1.5 h-4 w-4" /> Save
        </Button>
      }
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 2xl:grid-cols-5">
        <div className={cn(rowCls, "space-y-1.5 sm:col-span-2 2xl:col-span-2")}>
          <Label className="text-xs font-medium text-muted-foreground">Default Contract</Label>
          <select
            className={inputCls}
            value={local.default_underlying}
            onChange={(e) => setLocal((p) => ({ ...p, default_underlying: e.target.value }))}
          >
            {enabledMaps.length === 0 ? <option value="">No enabled contracts</option> : null}
            {enabledMaps.map((m) => (
              <option key={m.underlying} value={m.underlying}>
                {m.underlying} - {m.underlying_exchange}
              </option>
            ))}
          </select>
        </div>

        <div className={cn(rowCls, "space-y-1.5")}>
          <Label className="text-xs font-medium text-muted-foreground">Default Lots</Label>
          <input
            type="number"
            min={1}
            className={inputCls}
            value={local.default_lots}
            onChange={(e) => setLocal((p) => ({ ...p, default_lots: e.target.value }))}
          />
        </div>

        <div className={cn(rowCls, "space-y-1.5")}>
          <Label className="text-xs font-medium text-muted-foreground">Default SL Points</Label>
          <input
            type="number"
            min={0}
            step="0.5"
            className={inputCls}
            value={local.default_sl_points}
            onChange={(e) => setLocal((p) => ({ ...p, default_sl_points: e.target.value }))}
          />
        </div>

        <div className={cn(rowCls, "space-y-1.5")}>
          <Label className="text-xs font-medium text-muted-foreground">Default Product</Label>
          <select
            className={inputCls}
            value={local.default_product}
            onChange={(e) => setLocal((p) => ({ ...p, default_product: e.target.value }))}
          >
            <option value="MIS">MIS</option>
            <option value="NRML">NRML</option>
          </select>
        </div>
      </div>
      <div className={cn(rowCls, "flex flex-wrap items-center gap-2 text-xs text-muted-foreground")}>
        <span className="shrink-0">Auto-selected</span>
        <Badge variant="outline">Expiry: nearest listed</Badge>
        <Badge variant="outline">Strike: current ATM</Badge>
        <Badge variant="outline">Targets: template</Badge>
      </div>
    </AdminPanel>
  );
}

// ---------------------------------------------------------------------------
// Risk settings
// ---------------------------------------------------------------------------

function RiskSettings() {
  const qc = useQueryClient();
  const cfgQuery = useQuery({ queryKey: ["fr-config"], queryFn: getFrConfig });
  const [local, setLocal] = useState<Record<string, string>>({});

  useEffect(() => {
    if (cfgQuery.data) {
      const next: Record<string, string> = {};
      for (const s of SETTINGS) next[s.key] = cfgQuery.data[s.key]?.value ?? "";
      setLocal(next);
    }
  }, [cfgQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const changed = SETTINGS.filter((s) => local[s.key] !== (cfgQuery.data?.[s.key]?.value ?? ""));
      await Promise.all(changed.map((s) => setFrConfig(s.key, local[s.key])));
      return changed.length;
    },
    onSuccess: (n) => {
      toast.success(n ? `Saved ${n} setting(s)` : "No changes");
      qc.invalidateQueries({ queryKey: ["fr-config"] });
    },
    onError: (err: unknown) => {
      // @ts-expect-error axios error shape
      toast.error(String(err?.response?.data?.detail ?? "Save failed"));
    },
  });

  return (
    <AdminPanel
      title="Risk Engine"
      description="Automation, trailing stop-loss behavior, and polling cadence."
      className="h-full"
      action={
        <Button size="sm" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          <Save className="mr-1.5 h-4 w-4" /> Save
        </Button>
      }
    >
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {SETTINGS.map((s) => (
            <div key={s.key} className={cn(rowCls, "space-y-1.5")}>
              <div className="flex items-center justify-between gap-2">
                <Label className="truncate text-xs font-medium text-muted-foreground">{s.label}</Label>
                {s.type === "bool" ? (
                  <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
                    {(local[s.key] ?? "").toLowerCase() === "true" ? "On" : "Off"}
                  </Badge>
                ) : null}
              </div>
              {s.type === "bool" ? (
                <div className="flex h-8 items-center justify-between rounded-md border border-input bg-background px-2">
                  <span className="text-xs text-muted-foreground">Enabled</span>
                  <Switch
                    checked={(local[s.key] ?? "").toLowerCase() === "true"}
                    onCheckedChange={(checked) => setLocal((p) => ({ ...p, [s.key]: checked ? "true" : "false" }))}
                  />
                </div>
              ) : s.type === "select" ? (
                <select className={inputCls} value={local[s.key] ?? ""} onChange={(e) => setLocal((p) => ({ ...p, [s.key]: e.target.value }))}>
                  {s.options!.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={s.type === "number" ? "number" : "text"}
                  className={inputCls}
                  value={local[s.key] ?? ""}
                  onChange={(e) => setLocal((p) => ({ ...p, [s.key]: e.target.value }))}
                />
              )}
            </div>
          ))}
        </div>
    </AdminPanel>
  );
}

// ---------------------------------------------------------------------------
// Target levels
// ---------------------------------------------------------------------------

function TargetLevels() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["fr-targets"], queryFn: listTargets });
  const [rows, setRows] = useState<FrTemplateTarget[]>([]);
  const [newPts, setNewPts] = useState("");
  const [newPct, setNewPct] = useState("");

  useEffect(() => {
    if (query.data) setRows(query.data);
  }, [query.data]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["fr-targets"] });
  const onErr = (err: unknown) =>
    // @ts-expect-error axios error shape
    toast.error(String(err?.response?.data?.detail ?? "Failed"));

  const saveMut = useMutation({
    mutationFn: (r: FrTemplateTarget) => updateTarget(r.id, { points: r.points, exit_pct: r.exit_pct, enabled: r.enabled }),
    onSuccess: () => {
      toast.success("Target updated");
      invalidate();
    },
    onError: onErr,
  });
  const delMut = useMutation({
    mutationFn: (id: number) => deleteTarget(id),
    onSuccess: () => {
      toast.success("Target removed");
      invalidate();
    },
    onError: onErr,
  });
  const addMut = useMutation({
    mutationFn: () => createTarget(Number(newPts), Number(newPct), true),
    onSuccess: () => {
      toast.success("Target added");
      setNewPts("");
      setNewPct("");
      invalidate();
    },
    onError: onErr,
  });

  return (
    <AdminPanel
      title="Target Levels"
      description="Targets fire from futures-point movement; exit % is converted to whole lots."
    >
        <div className="hidden grid-cols-[2.5rem_1fr_1fr_auto_auto] items-center gap-2 px-1 text-[11px] text-muted-foreground sm:grid">
          <span>T#</span>
          <span>Points</span>
          <span>Exit %</span>
          <span>On</span>
          <span></span>
        </div>
        {rows.map((r, i) => (
          <div key={r.id} className={cn(rowCls, "grid grid-cols-2 items-end gap-2 sm:grid-cols-[2.5rem_1fr_1fr_auto_auto] sm:items-center")}>
            <span className="col-span-2 text-sm font-semibold text-muted-foreground sm:col-span-1">T{i + 1}</span>
            <div className="space-y-1 sm:space-y-0">
              <Label className="text-[10px] text-muted-foreground sm:hidden">Points</Label>
              <input
                type="number"
                className={inputCls}
                value={r.points}
                onChange={(e) =>
                  setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, points: Number(e.target.value) } : x)))
                }
              />
            </div>
            <div className="space-y-1 sm:space-y-0">
              <Label className="text-[10px] text-muted-foreground sm:hidden">Exit %</Label>
              <input
                type="number"
                className={inputCls}
                value={r.exit_pct}
                onChange={(e) =>
                  setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, exit_pct: Number(e.target.value) } : x)))
                }
              />
            </div>
            <label className="flex h-9 items-center justify-between rounded-md border border-input bg-background px-2 text-xs text-muted-foreground sm:w-16">
              On
              <Switch
                checked={r.enabled}
                onCheckedChange={(checked) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, enabled: checked } : x)))}
              />
            </label>
            <div className="flex justify-end gap-1">
              <Button size="xs" variant="outline" onClick={() => saveMut.mutate(r)}>
                <Save className="h-3.5 w-3.5" />
              </Button>
              <Button size="xs" variant="ghost" onClick={() => delMut.mutate(r.id)}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        ))}
        {/* Add row */}
        <div className={cn(rowCls, "grid grid-cols-2 items-end gap-2 border-dashed sm:grid-cols-[2.5rem_1fr_1fr_auto_auto] sm:items-center")}>
          <span className="col-span-2 text-sm font-semibold text-muted-foreground sm:col-span-1">New</span>
          <input type="number" placeholder="points" className={inputCls} value={newPts} onChange={(e) => setNewPts(e.target.value)} />
          <input type="number" placeholder="% exit" className={inputCls} value={newPct} onChange={(e) => setNewPct(e.target.value)} />
          <span className="hidden sm:block" />
          <Button className="col-span-2 sm:col-span-1" size="sm" disabled={!newPts || !newPct || addMut.isPending} onClick={() => addMut.mutate()}>
            <Plus className="mr-1.5 h-3.5 w-3.5" /> Add
          </Button>
        </div>
    </AdminPanel>
  );
}

// ---------------------------------------------------------------------------
// Symbol maps
// ---------------------------------------------------------------------------

const blankMap: Partial<FrSymbolMap> = {
  underlying: "",
  underlying_exchange: "NSE_INDEX",
  futures_symbol: "",
  futures_exchange: "NFO",
  lot_size: 0,
  auto_resolve: true,
  enabled: true,
};

function SymbolMaps() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["fr-symbol-maps"], queryFn: listSymbolMaps });
  const [rows, setRows] = useState<FrSymbolMap[]>([]);
  const [draft, setDraft] = useState<Partial<FrSymbolMap>>(blankMap);

  useEffect(() => {
    if (query.data) setRows(query.data);
  }, [query.data]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["fr-symbol-maps"] });
  const onErr = (err: unknown) =>
    // @ts-expect-error axios error shape
    toast.error(String(err?.response?.data?.detail ?? "Failed"));

  const saveMut = useMutation({
    mutationFn: (r: FrSymbolMap) =>
      updateSymbolMap(r.id, {
        underlying: r.underlying,
        underlying_exchange: r.underlying_exchange,
        futures_symbol: r.futures_symbol,
        futures_exchange: r.futures_exchange,
        lot_size: r.lot_size,
        auto_resolve: r.auto_resolve,
        enabled: r.enabled,
      }),
    onSuccess: () => {
      toast.success("Mapping saved");
      invalidate();
    },
    onError: onErr,
  });
  const delMut = useMutation({
    mutationFn: (id: number) => deleteSymbolMap(id),
    onSuccess: () => {
      toast.success("Mapping removed");
      invalidate();
    },
    onError: onErr,
  });
  const addMut = useMutation({
    mutationFn: () => createSymbolMap(draft),
    onSuccess: () => {
      toast.success("Mapping added");
      setDraft(blankMap);
      invalidate();
    },
    onError: onErr,
  });

  const headCls = "grid grid-cols-[1.4fr_1.4fr_1.4fr_1fr_.8fr_.8fr_auto] items-center gap-1.5";

  return (
    <AdminPanel
      title="Contract Mapping"
      description="Maps each underlying to the futures contract that drives stop-loss and target tracking."
    >
      <div className="scrollbar-hidden space-y-2 overflow-x-auto">
        <div className={cn(headCls, "min-w-[760px] px-1 text-[11px] text-muted-foreground")}>
          <span>Underlying</span>
          <span>Spot exch</span>
          <span>Futures sym (manual)</span>
          <span>Fut exch</span>
          <span>Auto</span>
          <span>On</span>
          <span></span>
        </div>
        {rows.map((r) => (
          <div key={r.id} className={cn(headCls, rowCls, "min-w-[760px]")}>
            <input className={inputCls} value={r.underlying} onChange={(e) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, underlying: e.target.value.toUpperCase() } : x)))} />
            <input className={inputCls} value={r.underlying_exchange} onChange={(e) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, underlying_exchange: e.target.value.toUpperCase() } : x)))} />
            <input
              className={cn(inputCls, r.auto_resolve && "opacity-50")}
              placeholder={r.auto_resolve ? "(auto)" : "e.g. NIFTY28AUG25FUT"}
              disabled={r.auto_resolve}
              value={r.futures_symbol ?? ""}
              onChange={(e) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, futures_symbol: e.target.value.toUpperCase() } : x)))}
            />
            <input className={inputCls} value={r.futures_exchange} onChange={(e) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, futures_exchange: e.target.value.toUpperCase() } : x)))} />
            <div className="flex justify-center">
              <Switch checked={r.auto_resolve} onCheckedChange={(checked) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, auto_resolve: checked } : x)))} />
            </div>
            <div className="flex justify-center">
              <Switch checked={r.enabled} onCheckedChange={(checked) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, enabled: checked } : x)))} />
            </div>
            <div className="flex justify-end gap-1">
              <Button size="xs" variant="outline" onClick={() => saveMut.mutate(r)}>
                <Save className="h-3.5 w-3.5" />
              </Button>
              <Button size="xs" variant="ghost" onClick={() => delMut.mutate(r.id)}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        ))}
        {/* Add row */}
        <div className={cn(headCls, rowCls, "min-w-[760px] border-dashed")}>
          <input className={inputCls} placeholder="RELIANCE" value={draft.underlying ?? ""} onChange={(e) => setDraft((d) => ({ ...d, underlying: e.target.value.toUpperCase() }))} />
          <input className={inputCls} value={draft.underlying_exchange ?? ""} onChange={(e) => setDraft((d) => ({ ...d, underlying_exchange: e.target.value.toUpperCase() }))} />
          <input className={cn(inputCls, draft.auto_resolve && "opacity-50")} disabled={draft.auto_resolve} placeholder={draft.auto_resolve ? "(auto)" : "FUT symbol"} value={draft.futures_symbol ?? ""} onChange={(e) => setDraft((d) => ({ ...d, futures_symbol: e.target.value.toUpperCase() }))} />
          <input className={inputCls} value={draft.futures_exchange ?? ""} onChange={(e) => setDraft((d) => ({ ...d, futures_exchange: e.target.value.toUpperCase() }))} />
          <div className="flex justify-center">
            <Switch checked={!!draft.auto_resolve} onCheckedChange={(checked) => setDraft((d) => ({ ...d, auto_resolve: checked }))} />
          </div>
          <div className="flex justify-center">
            <Switch checked={!!draft.enabled} onCheckedChange={(checked) => setDraft((d) => ({ ...d, enabled: checked }))} />
          </div>
          <Button size="sm" disabled={!draft.underlying || addMut.isPending} onClick={() => addMut.mutate()}>
            <Plus className="mr-1.5 h-3.5 w-3.5" /> Add
          </Button>
        </div>
      </div>
    </AdminPanel>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function FuturesRiskAdmin() {
  const { user } = useAuth();

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-xl font-bold tracking-tight sm:text-2xl">Futures-Risk Admin</h1>
          <p className="text-sm text-muted-foreground">
            Default quick-order setup, target template, stop-loss / trailing rules, and contract mapping.
          </p>
        </div>
        <Link to="/tools/futures-risk" className={cn(buttonVariants({ variant: "outline" }), "shrink-0 self-start sm:self-auto")}>
          <ArrowLeft className="mr-1 h-4 w-4" /> Dashboard
        </Link>
      </div>

      {!user?.is_admin ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Admin access required to manage Futures-Risk configuration.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(380px,0.75fr)]">
            <DefaultOrderSetup />
            <RiskSettings />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <TargetLevels />
            <SymbolMaps />
          </div>
        </>
      )}
    </div>
  );
}
