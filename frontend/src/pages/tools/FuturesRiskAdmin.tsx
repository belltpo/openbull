import { useEffect, useMemo, useState, type ReactNode } from "react";
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
  createTargetTemplate,
  createSymbolMap,
  deleteTargetTemplate,
  deleteSymbolMap,
  getFrConfig,
  listTargetTemplates,
  listSymbolMaps,
  setFrConfig,
  updateTargetTemplate,
  updateSymbolMap,
} from "@/api/futuresRisk";
import type { FrSymbolMap } from "@/types/futuresRisk";

const inputCls =
  "h-8 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25 dark:[color-scheme:dark]";
const rowCls = "rounded-md border border-border/60 bg-background/50 px-2.5 py-2";

type SettingType = "bool" | "number" | "text" | "select";
const SETTINGS: { key: string; label: string; type: SettingType; options?: string[] }[] = [
  { key: "auto_exit_enabled", label: "Auto-exit enabled", type: "bool" },
  { key: "trailing_enabled", label: "Trailing stop-loss enabled", type: "bool" },
  { key: "trailing_mode", label: "Trailing mode", type: "select", options: ["entry_after_t1", "prev_target", "off"] },
  { key: "poll_interval_sec", label: "Poll interval (sec)", type: "number" },
];

const DEFAULT_ORDER_KEYS = ["default_underlying", "default_lots", "default_sl_points", "default_product"] as const;
const emptyDefaultOrder = {
  default_underlying: "",
  default_lots: "",
  default_sl_points: "",
  default_product: "",
} satisfies Record<(typeof DEFAULT_ORDER_KEYS)[number], string>;

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
    <Card className={cn("self-start overflow-hidden rounded-lg border-border/70 bg-card/95 shadow-sm", className)}>
      <CardHeader className="flex flex-row items-start justify-between gap-3 border-b bg-muted/15 px-4 py-3">
        <div className="min-w-0">
          <CardTitle className="text-sm font-semibold tracking-tight">{title}</CardTitle>
          <CardDescription className="mt-0.5 text-xs leading-tight">{description}</CardDescription>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </CardHeader>
      <CardContent className={cn("space-y-3 p-4", contentClassName)}>{children}</CardContent>
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
  const enabledMaps = useMemo(
    () => (mapsQuery.data ?? []).filter((m) => m.enabled),
    [mapsQuery.data],
  );
  const [local, setLocal] = useState<Record<(typeof DEFAULT_ORDER_KEYS)[number], string>>(emptyDefaultOrder);

  useEffect(() => {
    if (!cfgQuery.data) return;
    setLocal({
      default_underlying: String(cfgQuery.data.default_underlying?.value || "").toUpperCase(),
      default_lots: cfgQuery.data.default_lots?.value ?? "",
      default_sl_points: cfgQuery.data.default_sl_points?.value ?? "",
      default_product: cfgQuery.data.default_product?.value ?? "",
    });
  }, [cfgQuery.data]);

  useEffect(() => {
    setLocal((prev) =>
      prev.default_underlying || enabledMaps.length === 0
        ? prev
        : { ...prev, default_underlying: enabledMaps[0].underlying },
    );
  }, [enabledMaps]);

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
      <div className="grid grid-cols-1 gap-3">
        <div className="space-y-1.5">
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

        <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label className="text-xs font-medium text-muted-foreground">Default Lots</Label>
          <input
            type="number"
            min={1}
            className={inputCls}
            value={local.default_lots}
            onChange={(e) => setLocal((p) => ({ ...p, default_lots: e.target.value }))}
          />
        </div>

        <div className="space-y-1.5">
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
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs font-medium text-muted-foreground">Default Product</Label>
          <input
            className={cn(inputCls, "uppercase")}
            value={local.default_product}
            onChange={(e) => setLocal((p) => ({ ...p, default_product: e.target.value.toUpperCase() }))}
          />
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
        <div className="grid grid-cols-1 gap-3">
          {SETTINGS.map((s) => (
            <div key={s.key} className="space-y-1.5">
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
// Target templates
// ---------------------------------------------------------------------------

function TargetLevels() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["fr-target-templates"], queryFn: listTargetTemplates });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [isDefault, setIsDefault] = useState(false);
  const [rows, setRows] = useState<{ points: number; exit_pct: number; enabled: boolean }[]>([]);

  useEffect(() => {
    const templates = query.data ?? [];
    if (templates.length === 0) return;
    if (selectedId && templates.some((t) => t.id === selectedId)) return;
    const preferred = templates.find((t) => t.is_default) ?? templates[0];
    setSelectedId(preferred.id);
  }, [query.data, selectedId]);

  const selected = useMemo(
    () => (query.data ?? []).find((t) => t.id === selectedId) ?? null,
    [query.data, selectedId],
  );

  useEffect(() => {
    if (!selected) return;
    setName(selected.name);
    setDescription(selected.description ?? "");
    setEnabled(selected.enabled);
    setIsDefault(selected.is_default);
    setRows(selected.targets.map((t) => ({ points: t.points, exit_pct: t.exit_pct, enabled: t.enabled })));
  }, [selected]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["fr-target-templates"] });
    qc.invalidateQueries({ queryKey: ["fr-targets"] });
  };
  const onErr = (err: unknown) =>
    // @ts-expect-error axios error shape
    toast.error(String(err?.response?.data?.detail ?? "Failed"));

  const saveMut = useMutation({
    mutationFn: () => {
      if (!selectedId) throw new Error("Select a target template first");
      return updateTargetTemplate(selectedId, {
        name,
        description,
        enabled,
        is_default: isDefault,
        targets: rows.filter((r) => r.points > 0),
      });
    },
    onSuccess: () => {
      toast.success("Target template saved");
      invalidate();
    },
    onError: onErr,
  });
  const delMut = useMutation({
    mutationFn: (id: number) => deleteTargetTemplate(id),
    onSuccess: () => {
      toast.success("Template removed");
      setSelectedId(null);
      invalidate();
    },
    onError: onErr,
  });
  const addMut = useMutation({
    mutationFn: () =>
      createTargetTemplate({
        name: "New Template",
        description: "",
        enabled: true,
        targets: [
          { points: 50, exit_pct: 25, enabled: true },
          { points: 100, exit_pct: 25, enabled: true },
        ],
      }),
    onSuccess: (template) => {
      toast.success("Template created");
      setSelectedId(template.id);
      invalidate();
    },
    onError: onErr,
  });

  const templates = query.data ?? [];
  const totalExit = rows.reduce((sum, r) => sum + (r.enabled ? Number(r.exit_pct) || 0 : 0), 0);

  return (
    <AdminPanel
      title="Target Templates"
      description="Create reusable target plans. New positions generate targets from the selected template."
      contentClassName="space-y-3"
      action={
        <div className="flex gap-1.5">
          <Button size="sm" variant="outline" onClick={() => addMut.mutate()} disabled={addMut.isPending}>
            <Plus className="mr-1.5 h-3.5 w-3.5" /> New
          </Button>
          <Button size="sm" onClick={() => saveMut.mutate()} disabled={!selectedId || saveMut.isPending}>
            <Save className="mr-1.5 h-3.5 w-3.5" /> Save
          </Button>
        </div>
      }
    >
      {templates.length === 0 ? (
        <div className={cn(rowCls, "flex items-center justify-between gap-3")}>
          <span className="text-sm text-muted-foreground">No target templates yet.</span>
          <Button size="sm" onClick={() => addMut.mutate()} disabled={addMut.isPending}>
            <Plus className="mr-1.5 h-3.5 w-3.5" /> Create
          </Button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 items-start gap-3 xl:grid-cols-[320px_minmax(0,1fr)_auto]">
            <div className="space-y-1.5">
              <Label className="text-xs font-medium text-muted-foreground">Template</Label>
              <select className={inputCls} value={selectedId ?? ""} onChange={(e) => setSelectedId(Number(e.target.value))}>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}{t.is_default ? " (default)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-medium text-muted-foreground">Name</Label>
              <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex h-full min-h-[52px] items-end gap-4 pb-1">
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <Switch checked={enabled} onCheckedChange={setEnabled} disabled={isDefault} />
                Enabled
              </label>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <Switch checked={isDefault} onCheckedChange={setIsDefault} />
                Default
              </label>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-muted-foreground">Description</Label>
            <input
              className={inputCls}
              placeholder="Optional note for this target plan"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="outline">{rows.filter((r) => r.enabled).length} active target(s)</Badge>
            <Badge variant={totalExit > 100 ? "destructive" : "outline"}>{totalExit}% planned exit</Badge>
          </div>

          <div className="hidden grid-cols-[3rem_minmax(140px,1fr)_minmax(120px,1fr)_4rem_2.25rem] items-center gap-2 rounded-md border border-border/50 bg-muted/20 px-2 py-1.5 text-[11px] text-muted-foreground sm:grid">
            <span>T#</span>
            <span>Points</span>
            <span>Exit %</span>
            <span>On</span>
            <span></span>
          </div>
          {rows.map((r, i) => (
            <div key={i} className="grid grid-cols-2 items-end gap-2 rounded-md border border-border/50 bg-background/50 px-2 py-2 sm:grid-cols-[3rem_minmax(140px,1fr)_minmax(120px,1fr)_4rem_2.25rem] sm:items-center">
              <span className="col-span-2 text-sm font-semibold text-muted-foreground sm:col-span-1">T{i + 1}</span>
              <input
                type="number"
                min={0}
                step="0.5"
                className={inputCls}
                value={r.points}
                onChange={(e) => setRows((rs) => rs.map((x, idx) => (idx === i ? { ...x, points: Number(e.target.value) } : x)))}
              />
              <input
                type="number"
                min={0}
                max={100}
                className={inputCls}
                value={r.exit_pct}
                onChange={(e) => setRows((rs) => rs.map((x, idx) => (idx === i ? { ...x, exit_pct: Number(e.target.value) } : x)))}
              />
              <label className="flex h-8 items-center justify-center rounded-md border border-input bg-background px-2 text-xs text-muted-foreground">
                <Switch checked={r.enabled} onCheckedChange={(checked) => setRows((rs) => rs.map((x, idx) => (idx === i ? { ...x, enabled: checked } : x)))} />
              </label>
              <div className="flex justify-end">
                <Button size="xs" variant="ghost" onClick={() => setRows((rs) => rs.filter((_, idx) => idx !== i))}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}
          <div className="flex flex-wrap justify-between gap-2">
            <Button size="sm" variant="outline" onClick={() => setRows((rs) => [...rs, { points: 0, exit_pct: 0, enabled: true }])}>
              <Plus className="mr-1.5 h-3.5 w-3.5" /> Add Target
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={!selectedId || isDefault || delMut.isPending}
              onClick={() => selectedId && delMut.mutate(selectedId)}
            >
              <Trash2 className="mr-1.5 h-3.5 w-3.5" /> Delete Template
            </Button>
          </div>
        </>
      )}
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

  const headCls = "grid grid-cols-[1.1fr_1.1fr_1.4fr_.8fr_4.5rem_4.5rem_4.25rem] items-center gap-2";

  return (
    <AdminPanel
      title="Contract Mapping"
      description="Maps each underlying to the futures contract that drives stop-loss and target tracking."
      contentClassName="p-0"
    >
      <div className="scrollbar-hidden overflow-x-auto">
        <div className={cn(headCls, "min-w-[860px] border-b bg-muted/20 px-4 py-2 text-[11px] text-muted-foreground")}>
          <span>Underlying</span>
          <span>Spot exch</span>
          <span>Futures sym (manual)</span>
          <span>Fut exch</span>
          <span>Auto</span>
          <span>On</span>
          <span></span>
        </div>
        <div className="space-y-2 p-4">
        {rows.map((r) => (
          <div key={r.id} className={cn(headCls, "min-w-[860px] rounded-md border border-border/50 bg-background/50 px-2.5 py-2")}>
            <input className={inputCls} value={r.underlying} onChange={(e) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, underlying: e.target.value.toUpperCase() } : x)))} />
            <input className={inputCls} value={r.underlying_exchange} onChange={(e) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, underlying_exchange: e.target.value.toUpperCase() } : x)))} />
            <input
              className={cn(inputCls, r.auto_resolve && "opacity-50")}
              placeholder={r.auto_resolve ? "(auto)" : "FUT symbol"}
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
        <div className={cn(headCls, "min-w-[860px] rounded-md border border-dashed border-border/70 bg-muted/10 px-2.5 py-2")}>
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
    <div className="mx-auto w-full max-w-[1500px] space-y-4">
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
          <div className="space-y-4">
            <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-2">
              <DefaultOrderSetup />
              <RiskSettings />
            </div>
            <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-2">
              <TargetLevels />
              <SymbolMaps />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
