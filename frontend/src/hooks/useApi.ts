import { useState, useEffect, useCallback, useRef } from "react";
import type {
  Server,
  MetricPoint,
  RunningService,
  CostOverview,
  CostHistoryPoint,
  Recommendation,
} from "@/types";

const BASE_URL = "/api";
const REFRESH_INTERVAL = 60_000; // 60 seconds

// ---------------------------------------------------------------------------
// Generic fetch helper
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function apiPost<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Generic hook with auto-refresh
// ---------------------------------------------------------------------------

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

function useAutoFetch<T>(
  fetchFn: () => Promise<T>,
  deps: unknown[] = [],
  autoRefresh = true
): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetch_ = useCallback(async () => {
    try {
      setLoading((prev) => (data === null ? true : prev));
      const result = await fetchFn();
      if (mountedRef.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mountedRef.current = true;
    fetch_();

    let interval: ReturnType<typeof setInterval> | undefined;
    if (autoRefresh) {
      interval = setInterval(fetch_, REFRESH_INTERVAL);
    }

    return () => {
      mountedRef.current = false;
      if (interval) clearInterval(interval);
    };
  }, [fetch_, autoRefresh]);

  return { data, loading, error, refetch: fetch_ };
}

// ---------------------------------------------------------------------------
// Typed hooks
// ---------------------------------------------------------------------------

export function useServers(source?: string, search?: string) {
  const result = useAutoFetch<Server[]>(() => {
    const params = new URLSearchParams();
    if (source && source !== "all") params.set("source", source);
    if (search) params.set("search", search);
    const qs = params.toString();
    return apiFetch<Server[]>(`/servers${qs ? `?${qs}` : ""}`);
  }, [source, search]);

  return {
    servers: result.data,
    loading: result.loading,
    error: result.error,
    refetch: result.refetch,
  };
}

export function useServer(id: number | null) {
  const result = useAutoFetch<Server>(
    () => apiFetch<Server>(`/servers/${id}`),
    [id],
    id !== null
  );

  return {
    server: result.data,
    loading: result.loading,
    error: result.error,
  };
}

export function useMetrics(serverId: number | null, period: string) {
  const result = useAutoFetch<MetricPoint[]>(
    () => apiFetch<MetricPoint[]>(`/servers/${serverId}/metrics?period=${period}`),
    [serverId, period],
    serverId !== null
  );

  return {
    metrics: result.data,
    loading: result.loading,
  };
}

export function useServices(serverId: number | null) {
  const result = useAutoFetch<RunningService[]>(
    () => apiFetch<RunningService[]>(`/servers/${serverId}/services`),
    [serverId],
    serverId !== null
  );

  return {
    services: result.data,
    loading: result.loading,
  };
}

export function useCostOverview() {
  const result = useAutoFetch<CostOverview>(() =>
    apiFetch<CostOverview>("/costs/overview")
  );

  return {
    costs: result.data,
    loading: result.loading,
  };
}

export function useCostHistory() {
  const result = useAutoFetch<CostHistoryPoint[]>(() =>
    apiFetch<CostHistoryPoint[]>("/costs/history")
  );

  return {
    history: result.data,
    loading: result.loading,
  };
}

export function useRecommendations() {
  const result = useAutoFetch<Recommendation[]>(() =>
    apiFetch<Recommendation[]>("/recommendations")
  );

  return {
    recommendations: result.data,
    loading: result.loading,
    refetch: result.refetch,
  };
}

// ---------------------------------------------------------------------------
// Action functions (non-hook)
// ---------------------------------------------------------------------------

export async function dismissRecommendation(id: number): Promise<void> {
  await apiPost(`/recommendations/${id}/dismiss`);
}

export async function acceptRecommendation(id: number): Promise<void> {
  await apiPost(`/recommendations/${id}/accept`);
}
