import { useState } from "react";
import { ExternalLink, Zap } from "lucide-react";

import { cn } from "@/lib/utils";
import { FuturesRiskOrderPopup } from "@/components/futures-risk/OrderPopup";

/**
 * Global quick-order launcher — a floating control present on every page so a
 * Buy/Sell CE/PE order can be placed from anywhere in OpenBull. The arrow
 * button pops the same order ticket out into a separate, resizable browser
 * window (second-monitor friendly) via /quick-order.
 */
export function QuickOrderLauncher() {
  const [open, setOpen] = useState(false);

  const popOut = () => {
    window.open(
      "/quick-order",
      "openbull-quick-order",
      "width=520,height=780,menubar=no,toolbar=no,location=no,status=no,resizable=yes",
    );
  };

  return (
    <>
      <div className="fixed bottom-5 right-5 z-50 flex items-center gap-2">
        <button
          type="button"
          onClick={popOut}
          title="Pop out as a separate window"
          aria-label="Pop out order ticket"
          className={cn(
            "inline-flex h-10 w-10 items-center justify-center rounded-full border border-border bg-card text-foreground shadow-md transition-colors",
            "hover:bg-muted",
          )}
        >
          <ExternalLink className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="Quick order — Buy / Sell CE / PE"
          className={cn(
            "inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-lg transition-transform",
            "hover:scale-[1.03] active:scale-95",
          )}
        >
          <Zap className="h-4 w-4" />
          Quick Order
        </button>
      </div>

      <FuturesRiskOrderPopup open={open} onOpenChange={setOpen} />
    </>
  );
}
