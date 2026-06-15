import { useState } from "react";

import { FuturesRiskOrderPopup } from "@/components/futures-risk/OrderPopup";

/**
 * Standalone, detached order-ticket window (opened via window.open from the
 * QuickOrderLauncher). Renders just the Buy/Sell CE/PE popup so it can live on
 * a second monitor. Re-opens itself after each placement so multiple orders
 * can be fired without reopening the window.
 */
export default function QuickOrderWindow() {
  const [open, setOpen] = useState(true);

  return (
    <div className="min-h-screen bg-background">
      <FuturesRiskOrderPopup
        open={open}
        onOpenChange={(v) => {
          // Keep the ticket available for the next order in this dedicated window.
          setOpen(true);
          void v;
        }}
      />
    </div>
  );
}
