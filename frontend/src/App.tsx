import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { TradingModeProvider } from "@/contexts/TradingModeContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { AppLayout } from "@/components/layout/AppLayout";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Setup from "@/pages/Setup";
import Dashboard from "@/pages/Dashboard";
import BrokerConfig from "@/pages/BrokerConfig";
import BrokerSelect from "@/pages/BrokerSelect";
import BrokerAngelLogin from "@/pages/BrokerAngelLogin";
import BrokerDhanToken from "@/pages/BrokerDhanToken";
import QuickOrderWindow from "@/pages/QuickOrderWindow";
import ApiKey from "@/pages/ApiKey";
import OrderBook from "@/pages/OrderBook";
import TradeBook from "@/pages/TradeBook";
import Positions from "@/pages/Positions";
import Holdings from "@/pages/Holdings";
import Search from "@/pages/Search";
import WebSocketTest from "@/pages/WebSocketTest";
import Logs from "@/pages/Logs";
import Sandbox from "@/pages/Sandbox";
import SandboxMyPnL from "@/pages/SandboxMyPnL";
import Tools from "@/pages/Tools";
import NotFound from "@/pages/NotFound";
import { Toaster } from "@/components/ui/sonner";

// Code-split heavy tool pages — Plotly weighs ~600 KB gz, only fetch it when
// the user navigates to a chart tool.
const OptionChain = lazy(() => import("@/pages/tools/OptionChain"));
const OITracker = lazy(() => import("@/pages/tools/OITracker"));
const MaxPain = lazy(() => import("@/pages/tools/MaxPain"));
const OptionGreeks = lazy(() => import("@/pages/tools/OptionGreeks"));
const IVSmile = lazy(() => import("@/pages/tools/IVSmile"));
const VolSurface = lazy(() => import("@/pages/tools/VolSurface"));
const StraddleChart = lazy(() => import("@/pages/tools/StraddleChart"));
const GEXDashboard = lazy(() => import("@/pages/tools/GEXDashboard"));
const StrategyBuilder = lazy(() => import("@/pages/tools/StrategyBuilder"));
const StrategyPortfolio = lazy(() => import("@/pages/tools/StrategyPortfolio"));
const StraddlesStrangleChain = lazy(
  () => import("@/pages/tools/StraddlesStrangleChain"),
);
const FuturesRisk = lazy(() => import("@/pages/tools/FuturesRisk"));
const FuturesRiskAdmin = lazy(() => import("@/pages/tools/FuturesRiskAdmin"));
const FuturesRiskCardDemo = lazy(() => import("@/pages/tools/FuturesRiskCardDemo"));
const StrategyList = lazy(() => import("@/pages/strategy/List"));
const StrategyWizard = lazy(() => import("@/pages/strategy/Wizard"));
const StrategyDetail = lazy(() => import("@/pages/strategy/Detail"));
const StrategyEdit = lazy(() => import("@/pages/strategy/Edit"));
const Playground = lazy(() => import("@/pages/Playground"));

function ToolFallback() {
  return null;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
      gcTime: 30 * 60_000,
    },
  },
});

function RoutePreloader() {
  const { user } = useAuth();
  useEffect(() => {
    if (!user) return;
    const preload = () => {
      void Promise.allSettled([
        import("@/pages/tools/OptionChain"), import("@/pages/tools/OITracker"),
        import("@/pages/tools/MaxPain"), import("@/pages/tools/OptionGreeks"),
        import("@/pages/tools/IVSmile"), import("@/pages/tools/VolSurface"),
        import("@/pages/tools/StraddleChart"), import("@/pages/tools/GEXDashboard"),
        import("@/pages/tools/StrategyBuilder"), import("@/pages/tools/StrategyPortfolio"),
        import("@/pages/tools/StraddlesStrangleChain"), import("@/pages/tools/FuturesRisk"),
        import("@/pages/tools/FuturesRiskAdmin"), import("@/pages/strategy/List"),
        import("@/pages/strategy/Wizard"), import("@/pages/strategy/Detail"),
      ]);
    };
    if ("requestIdleCallback" in window) {
      const idleId = window.requestIdleCallback(preload, { timeout: 5000 });
      return () => window.cancelIdleCallback(idleId);
    }
    const timer = globalThis.setTimeout(preload, 1500);
    return () => globalThis.clearTimeout(timer);
  }, [user]);
  return null;
}

function App() {

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <AuthProvider>
            <RoutePreloader />
            <TradingModeProvider>
              <Routes>
              {/* Public routes */}
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/setup" element={<Setup />} />

              {/* Broker select (protected, no layout) */}
              <Route
                path="/broker/select"
                element={
                  <ProtectedRoute>
                    <BrokerSelect />
                  </ProtectedRoute>
                }
              />

              {/* Angel One credentials/TOTP login (no OAuth) */}
              <Route
                path="/broker/angel/totp"
                element={
                  <ProtectedRoute>
                    <BrokerAngelLogin />
                  </ProtectedRoute>
                }
              />

              {/* Dhan personal access-token login (no Partner app) */}
              <Route
                path="/broker/dhan/token"
                element={
                  <ProtectedRoute>
                    <BrokerDhanToken />
                  </ProtectedRoute>
                }
              />

              {/* Detached quick-order ticket — standalone window (window.open). */}
              <Route
                path="/quick-order"
                element={
                  <ProtectedRoute requiresBroker>
                    <QuickOrderWindow />
                  </ProtectedRoute>
                }
              />

              {/* Playground — full-screen, no AppLayout. Owns its own header. */}
              <Route
                path="/playground"
                element={
                  <ProtectedRoute requiresBroker>
                    <Suspense fallback={<ToolFallback />}>
                      <Playground />
                    </Suspense>
                  </ProtectedRoute>
                }
              />

              {/* Protected routes with layout */}
              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Dashboard />
                    </ProtectedRoute>
                  }
                />
                <Route path="/broker/config" element={<BrokerConfig />} />
                <Route path="/apikey" element={<ApiKey />} />
                <Route
                  path="/search"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Search />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/orderbook"
                  element={
                    <ProtectedRoute requiresBroker>
                      <OrderBook />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tradebook"
                  element={
                    <ProtectedRoute requiresBroker>
                      <TradeBook />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/positions"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Positions />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/holdings"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Holdings />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/websocket/test"
                  element={
                    <ProtectedRoute requiresBroker>
                      <WebSocketTest />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/logs"
                  element={
                    <ProtectedRoute>
                      <Logs />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/sandbox"
                  element={
                    <ProtectedRoute>
                      <Sandbox />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/sandbox/mypnl"
                  element={
                    <ProtectedRoute>
                      <SandboxMyPnL />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Tools />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/optionchain"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <OptionChain />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/oitracker"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <OITracker />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/maxpain"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <MaxPain />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/greeks"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <OptionGreeks />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/ivsmile"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <IVSmile />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/volsurface"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <VolSurface />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/straddle"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <StraddleChart />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/gex"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <GEXDashboard />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/straddles-strangle-chain"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <StraddlesStrangleChain />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/strategybuilder"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <StrategyBuilder />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/strategyportfolio"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <StrategyPortfolio />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/futures-risk"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <FuturesRisk />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/futures-risk/admin"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <FuturesRiskAdmin />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tools/futures-risk/card-demo"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <FuturesRiskCardDemo />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/strategy"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <StrategyList />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/strategy/new"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <StrategyWizard />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/strategy/:id"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <StrategyDetail />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/strategy/:id/edit"
                  element={
                    <ProtectedRoute requiresBroker>
                      <Suspense fallback={<ToolFallback />}>
                        <StrategyEdit />
                      </Suspense>
                    </ProtectedRoute>
                  }
                />
              </Route>

              {/* Catch-all */}
              <Route path="*" element={<NotFound />} />
            </Routes>
            <Toaster />
            </TradingModeProvider>
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
