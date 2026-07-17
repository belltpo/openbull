import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "@/contexts/AuthContext";

interface ProtectedRouteProps {
  children: ReactNode;
  requiresBroker?: boolean;
}

export function ProtectedRoute({ children, requiresBroker = false }: ProtectedRouteProps) {
  const { user, loading } = useAuth();

  if (loading) {
    // Avoid blocking every route with a full-screen spinner during the brief
    // cold-start session verification. Navigations reuse the query cache.
    return null;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (requiresBroker && !user.broker_authenticated) {
    return <Navigate to="/broker/select" replace />;
  }

  return <>{children}</>;
}
