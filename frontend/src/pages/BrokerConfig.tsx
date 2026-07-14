import { useState, useEffect, useMemo } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { listBrokers, getBrokerCredentials, saveBrokerCredentials } from "@/api/broker";
import type { BrokerConfigData } from "@/types/broker";

type BrokerHelp = {
  apiKeyLabel: string;
  apiKeyHint: string;
  apiSecretLabel: string;
  apiSecretHint: string;
  redirectHint: string;
  showApiSecret: boolean;
  showRedirect: boolean;
  showClientId: boolean;
  clientIdLabel?: string;
  clientIdHint?: string;
  banner?: string;
};

const DEFAULT_HELP: BrokerHelp = {
  apiKeyLabel: "API Key",
  apiKeyHint: "From your broker developer portal.",
  apiSecretLabel: "API Secret",
  apiSecretHint: "From your broker developer portal.",
  redirectHint: "Must exactly match the URL whitelisted on the broker portal.",
  showApiSecret: true,
  showRedirect: true,
  showClientId: false,
};

const HELP_BY_BROKER: Record<string, BrokerHelp> = {
  upstox: {
    ...DEFAULT_HELP,
    redirectHint: "e.g. http://127.0.0.1:8000/upstox/callback (must match Upstox app config).",
  },
  zerodha: {
    ...DEFAULT_HELP,
    apiKeyLabel: "API Key",
    apiKeyHint: "Kite Connect API key from developers.kite.trade.",
    redirectHint: "e.g. http://127.0.0.1:8000/zerodha/callback (must match Kite Connect app).",
  },
  fyers: {
    ...DEFAULT_HELP,
    apiKeyLabel: "App ID",
    apiKeyHint: "From myapi.fyers.in (e.g. ABC123-100).",
    redirectHint: "e.g. http://127.0.0.1:8000/fyers/callback (must match Fyers app config).",
  },
  dhan: {
    apiKeyLabel: "App ID (API Key)",
    apiKeyHint: "Dhan Partner App ID / API ID from your Dhan app.",
    apiSecretLabel: "App Secret",
    apiSecretHint: "Dhan Partner App Secret from your Dhan app.",
    redirectHint: "Use http://127.0.0.1:8000/dhan/callback and make sure the same URL is saved in Dhan.",
    showApiSecret: true,
    showRedirect: true,
    showClientId: true,
    clientIdLabel: "Dhan Client ID",
    clientIdHint: "Your Dhan client ID. It is required to generate the consent login URL.",
    banner:
      "For Dhan API login, save App ID, App Secret, Client ID, and redirect URL here, then click Login with Dhan API on the broker selection page. Access-token login is still available as an alternate path.",
  },
  angel: {
    apiKeyLabel: "SmartAPI Key",
    apiKeyHint: "From smartapi.angelbroking.com (the X-PrivateKey for your trading app).",
    apiSecretLabel: "API Secret (unused)",
    apiSecretHint: "Angel SmartAPI does not require a secret -- you can leave this blank.",
    redirectHint: "Angel does not OAuth, so the redirect URL is unused (you can leave it blank).",
    showApiSecret: false,
    showRedirect: false,
    showClientId: false,
    banner:
      "Angel One does not use OAuth. After saving the API Key, click Login with Angel One on the broker page and enter your Client Code, MPIN and TOTP.",
  },
};

export default function BrokerConfig() {
  const [selectedBroker, setSelectedBroker] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [redirectUrl, setRedirectUrl] = useState("");
  const [clientId, setClientId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: brokers, isLoading: brokersLoading } = useQuery({
    queryKey: ["brokers"],
    queryFn: listBrokers,
  });

  const help = useMemo(
    () => (selectedBroker ? HELP_BY_BROKER[selectedBroker] ?? DEFAULT_HELP : DEFAULT_HELP),
    [selectedBroker],
  );

  useEffect(() => {
    if (!selectedBroker) return;
    setMessage("");
    setError("");
    getBrokerCredentials(selectedBroker)
      .then((creds) => {
        setApiKey(creds.api_key || "");
        setApiSecret(creds.api_secret || "");
        setRedirectUrl(creds.redirect_url || "");
        setClientId(creds.client_id || "");
      })
      .catch(() => {
        setApiKey("");
        setApiSecret("");
        setRedirectUrl("");
        setClientId("");
      });
  }, [selectedBroker]);

  const saveMutation = useMutation({
    mutationFn: (data: BrokerConfigData) => saveBrokerCredentials(data),
    onSuccess: () => {
      setMessage("Broker credentials saved successfully.");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["brokers"] });
    },
    onError: (err: unknown) => {
      const axiosErr = err as { response?: { data?: { detail?: string | Array<{ msg: string }> } } };
      const detail = axiosErr.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg).join(", "));
      } else {
        setError(detail ?? "Failed to save credentials.");
      }
      setMessage("");
    },
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!selectedBroker) {
      setError("Please select a broker.");
      return;
    }
    const isConfigured =
      brokers?.find((b) => b.name === selectedBroker)?.is_configured ?? false;
    if (!isConfigured && help.showClientId && !clientId.trim()) {
      setError(`${help.clientIdLabel} is required for ${selectedBroker}.`);
      return;
    }
    saveMutation.mutate({
      broker: selectedBroker,
      api_key: apiKey,
      api_secret: help.showApiSecret ? apiSecret : "",
      redirect_url: help.showRedirect ? redirectUrl : "",
      client_id: help.showClientId ? clientId.trim() : undefined,
    });
  };

  if (brokersLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-primary" />
          <p className="text-sm text-muted-foreground">Loading brokers...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Broker Configuration</h1>
        <p className="text-sm text-muted-foreground">
          Configure your broker API credentials
        </p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>API Credentials</CardTitle>
          <CardDescription>
            Select a broker and enter your API credentials
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {message && (
              <div className="rounded-md bg-green-600/10 p-3 text-sm text-green-700 dark:text-green-400">
                {message}
              </div>
            )}
            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="broker-select">Broker</Label>
              <Select
                value={selectedBroker}
                onValueChange={setSelectedBroker}
              >
                <SelectTrigger id="broker-select" className="h-8 rounded-lg px-2.5 dark:bg-input/30">
                  <SelectValue placeholder="Select a broker..." />
                </SelectTrigger>
                <SelectContent align="start" alignItemWithTrigger={false}>
                  {brokers?.map((b) => (
                    <SelectItem key={b.name} value={b.name}>
                      {b.display_name}
                      {b.is_configured ? " (Configured)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {selectedBroker && (() => {
              const isConfigured =
                brokers?.find((b) => b.name === selectedBroker)?.is_configured ?? false;
              const keepHint = "Leave blank to keep the saved value.";
              return (
              <>
                {isConfigured && <Badge variant="secondary">Currently Configured</Badge>}

                {help.banner && (
                  <div className="rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
                    {help.banner}
                  </div>
                )}

                {help.showClientId && (
                  <div className="space-y-2">
                    <Label htmlFor="client-id">{help.clientIdLabel}</Label>
                    <Input
                      id="client-id"
                      type="text"
                      value={clientId}
                      onChange={(e) => setClientId(e.target.value)}
                      placeholder="e.g. 1100123456"
                      required={!isConfigured}
                    />
                    {help.clientIdHint && (
                      <p className="text-xs text-muted-foreground">
                        {help.clientIdHint}
                        {isConfigured ? ` ${keepHint}` : ""}
                      </p>
                    )}
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="api-key">{help.apiKeyLabel}</Label>
                  <Input
                    id="api-key"
                    type="text"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={isConfigured ? "Leave blank to keep saved value" : `Enter ${help.apiKeyLabel}`}
                    required={!isConfigured}
                  />
                  <p className="text-xs text-muted-foreground">
                    {help.apiKeyHint}
                    {isConfigured ? ` ${keepHint}` : ""}
                  </p>
                </div>

                {help.showApiSecret && (
                  <div className="space-y-2">
                    <Label htmlFor="api-secret">{help.apiSecretLabel}</Label>
                    <PasswordInput
                      id="api-secret"
                      value={apiSecret}
                      onChange={(e) => setApiSecret(e.target.value)}
                      placeholder={isConfigured ? "Leave blank to keep saved value" : `Enter ${help.apiSecretLabel}`}
                      required={!isConfigured}
                    />
                    <p className="text-xs text-muted-foreground">
                      {help.apiSecretHint}
                      {isConfigured ? ` ${keepHint}` : ""}
                    </p>
                  </div>
                )}

                {help.showRedirect && (
                  <div className="space-y-2">
                    <Label htmlFor="redirect-url">Redirect URL</Label>
                    <Input
                      id="redirect-url"
                      type="url"
                      value={redirectUrl}
                      onChange={(e) => setRedirectUrl(e.target.value)}
                      placeholder="http://127.0.0.1:8000/<broker>/callback"
                      required={!isConfigured}
                    />
                    <p className="text-xs text-muted-foreground">
                      {help.redirectHint}
                      {isConfigured ? ` ${keepHint}` : ""}
                    </p>
                  </div>
                )}

                <Button
                  type="submit"
                  disabled={saveMutation.isPending}
                >
                  {saveMutation.isPending ? "Saving..." : "Save Credentials"}
                </Button>
                {selectedBroker === "dhan" && (
                  <Button type="button" variant="outline" onClick={() => navigate("/broker/dhan/token")}>
                    Use Access Token Instead
                  </Button>
                )}
              </>
              );
            })()}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
