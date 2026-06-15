import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Plus, Save, Trash2 } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
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
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3";

type SettingType = "bool" | "number" | "text" | "select";
const SETTINGS: { key: string; label: string; type: SettingType; options?: string[] }[] = [
  { key: "auto_exit_enabled", label: "Auto-exit enabled", type: "bool" },
  { key: "trailing_enabled", label: "Trailing stop-loss enabled", type: "bool" },
  { key: "trailing_mode", label: "Trailing mode", type: "select", options: ["entry_after_t1", "prev_target", "off"] },
  { key: "default_sl_points", label: "Default SL points", type: "number" },
  { key: "default_lots", label: "Default lots", type: "number" },
  { key: "default_product", label: "Default product", type: "select", options: ["MIS", "NRML"] },
  { key: "poll_interval_sec", label: "Poll interval (sec)", type: "number" },
];

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
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Risk Settings</CardTitle>
        <CardDescription>Global defaults for new trades and the auto-exit engine.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {SETTINGS.map((s) => (
            <div key={s.key} className="space-y-1">
              <Label className="text-xs">{s.label}</Label>
              {s.type === "bool" ? (
                <label className="flex h-8 items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={(local[s.key] ?? "").toLowerCase() === "true"}
                    onChange={(e) => setLocal((p) => ({ ...p, [s.key]: e.target.checked ? "true" : "false" }))}
                    className="h-4 w-4"
                  />
                  <span className="text-muted-foreground">{(local[s.key] ?? "").toLowerCase() === "true" ? "On" : "Off"}</span>
                </label>
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
        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          <Save className="mr-1 h-4 w-4" /> Save settings
        </Button>
      </CardContent>
    </Card>
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
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Target Levels</CardTitle>
        <CardDescription>
          Each target fires when the futures price moves this many points; the % is exited (whole lots).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="grid grid-cols-[2.5rem_1fr_1fr_auto_auto] items-center gap-2 text-[11px] text-muted-foreground">
          <span>T#</span>
          <span>Points</span>
          <span>Exit %</span>
          <span>On</span>
          <span></span>
        </div>
        {rows.map((r, i) => (
          <div key={r.id} className="grid grid-cols-[2.5rem_1fr_1fr_auto_auto] items-center gap-2">
            <span className="text-sm font-medium text-muted-foreground">T{i + 1}</span>
            <input
              type="number"
              className={inputCls}
              value={r.points}
              onChange={(e) =>
                setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, points: Number(e.target.value) } : x)))
              }
            />
            <input
              type="number"
              className={inputCls}
              value={r.exit_pct}
              onChange={(e) =>
                setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, exit_pct: Number(e.target.value) } : x)))
              }
            />
            <input
              type="checkbox"
              checked={r.enabled}
              onChange={(e) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, enabled: e.target.checked } : x)))}
              className="h-4 w-4"
            />
            <div className="flex gap-1">
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
        <div className="grid grid-cols-[2.5rem_1fr_1fr_auto_auto] items-center gap-2 border-t pt-2">
          <span className="text-sm font-medium text-muted-foreground">+</span>
          <input type="number" placeholder="points" className={inputCls} value={newPts} onChange={(e) => setNewPts(e.target.value)} />
          <input type="number" placeholder="% exit" className={inputCls} value={newPct} onChange={(e) => setNewPct(e.target.value)} />
          <span />
          <Button size="xs" disabled={!newPts || !newPct || addMut.isPending} onClick={() => addMut.mutate()}>
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
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
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Underlying → Futures Mapping</CardTitle>
        <CardDescription>
          The futures contract whose price drives target/SL. Auto-resolve picks the current-month FUT from the master.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 overflow-x-auto">
        <div className={cn(headCls, "min-w-[640px] text-[11px] text-muted-foreground")}>
          <span>Underlying</span>
          <span>Spot exch</span>
          <span>Futures sym (manual)</span>
          <span>Fut exch</span>
          <span>Auto</span>
          <span>On</span>
          <span></span>
        </div>
        {rows.map((r) => (
          <div key={r.id} className={cn(headCls, "min-w-[640px]")}>
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
            <input type="checkbox" className="mx-auto h-4 w-4" checked={r.auto_resolve} onChange={(e) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, auto_resolve: e.target.checked } : x)))} />
            <input type="checkbox" className="mx-auto h-4 w-4" checked={r.enabled} onChange={(e) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, enabled: e.target.checked } : x)))} />
            <div className="flex gap-1">
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
        <div className={cn(headCls, "min-w-[640px] border-t pt-2")}>
          <input className={inputCls} placeholder="RELIANCE" value={draft.underlying ?? ""} onChange={(e) => setDraft((d) => ({ ...d, underlying: e.target.value.toUpperCase() }))} />
          <input className={inputCls} value={draft.underlying_exchange ?? ""} onChange={(e) => setDraft((d) => ({ ...d, underlying_exchange: e.target.value.toUpperCase() }))} />
          <input className={cn(inputCls, draft.auto_resolve && "opacity-50")} disabled={draft.auto_resolve} placeholder={draft.auto_resolve ? "(auto)" : "FUT symbol"} value={draft.futures_symbol ?? ""} onChange={(e) => setDraft((d) => ({ ...d, futures_symbol: e.target.value.toUpperCase() }))} />
          <input className={inputCls} value={draft.futures_exchange ?? ""} onChange={(e) => setDraft((d) => ({ ...d, futures_exchange: e.target.value.toUpperCase() }))} />
          <input type="checkbox" className="mx-auto h-4 w-4" checked={!!draft.auto_resolve} onChange={(e) => setDraft((d) => ({ ...d, auto_resolve: e.target.checked }))} />
          <input type="checkbox" className="mx-auto h-4 w-4" checked={!!draft.enabled} onChange={(e) => setDraft((d) => ({ ...d, enabled: e.target.checked }))} />
          <Button size="xs" disabled={!draft.underlying || addMut.isPending} onClick={() => addMut.mutate()}>
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function FuturesRiskAdmin() {
  const { user } = useAuth();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Futures-Risk Admin</h1>
          <p className="text-sm text-muted-foreground">
            Target template, stop-loss / trailing rules, and underlying → futures symbol mapping.
          </p>
        </div>
        <Link to="/tools/futures-risk" className={cn(buttonVariants({ variant: "outline" }))}>
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
          <RiskSettings />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <TargetLevels />
            <SymbolMaps />
          </div>
        </>
      )}
    </div>
  );
}
