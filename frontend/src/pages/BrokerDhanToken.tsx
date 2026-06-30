import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { dhanTokenLogin } from "@/api/broker";

export default function BrokerDhanToken() {
  const [accessToken, setAccessToken] = useState("");
  const [clientId, setClientId] = useState("");

  const mutation = useMutation({
    mutationFn: () => dhanTokenLogin({ access_token: accessToken.trim(), client_id: clientId.trim() }),
    onSuccess: () => {
      toast.success("Dhan connected");
      // Full reload so the new broker-claim cookie + auth state are picked up.
      window.location.href = "/dashboard";
    },
    onError: (err: unknown) => {
      // @ts-expect-error axios error shape
      toast.error(String(err?.response?.data?.detail ?? "Dhan authentication failed"));
    },
  });

  const canSubmit = accessToken.trim().length > 50 && clientId.trim().length > 0 && !mutation.isPending;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Connect Dhan</CardTitle>
          <CardDescription>
            Paste your personal DhanHQ <strong>access token</strong> and <strong>Client ID</strong>. No partner app
            required.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="client-id" className="text-xs">
              Dhan Client ID
            </Label>
            <Input
              id="client-id"
              placeholder="e.g. 1100123456"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="access-token" className="text-xs">
              Access Token (JWT)
            </Label>
            <textarea
              id="access-token"
              placeholder="Paste the long access token from web.dhan.co → DhanHQ Trading API"
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
              rows={5}
              className="w-full resize-y rounded-lg border border-input bg-transparent px-3 py-2 font-mono text-xs outline-none focus-visible:border-ring focus-visible:ring-3"
            />
          </div>

          <Button className="w-full" disabled={!canSubmit} onClick={() => mutation.mutate()}>
            {mutation.isPending ? "Connecting…" : "Connect Dhan"}
          </Button>

          <div className="rounded-lg bg-muted/40 p-3 text-[11px] leading-relaxed text-muted-foreground">
            <p className="font-medium text-foreground">Where to get these</p>
            <p className="mt-1">
              web.dhan.co → Profile → <strong>DhanHQ Trading API</strong> → generate an access token. Your Client ID is
              your Dhan account number (~10 digits).
            </p>
          </div>

          <div className="text-center text-xs text-muted-foreground">
            Have a Partner app instead?{" "}
            <Link to="/broker/config" className="font-medium text-primary underline underline-offset-4">
              Use App ID / Secret
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
