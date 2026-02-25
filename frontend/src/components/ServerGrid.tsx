import { useState, useMemo } from "react";
import type { Server } from "@/types";
import { useServers } from "@/hooks/useApi";
import ServerCard from "./ServerCard";

interface ServerGridProps {
  onSelectServer: (id: number) => void;
}

type SortOption = "name" | "cost" | "cpu";

export default function ServerGrid({ onSelectServer }: ServerGridProps) {
  const [source, setSource] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortOption>("name");

  const { servers, loading, error } = useServers(source, search);

  const sorted = useMemo(() => {
    if (!servers) return [];
    const list = [...servers];
    switch (sort) {
      case "name":
        list.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case "cost":
        list.sort((a, b) => b.monthly_cost_eur - a.monthly_cost_eur);
        break;
      case "cpu":
        list.sort(
          (a, b) =>
            (b.metrics?.cpu_percent ?? 0) - (a.metrics?.cpu_percent ?? 0)
        );
        break;
    }
    return list;
  }, [servers, sort]);

  return (
    <section>
      {/* Header + Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-text-primary text-lg font-semibold">
          Servers
          {servers && (
            <span className="text-text-secondary text-sm font-normal ml-2">
              ({servers.length})
            </span>
          )}
        </h2>

        <div className="flex items-center gap-2">
          {/* Source filter */}
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="bg-input border border-border text-text-primary text-xs rounded-md px-2.5 py-1.5 focus:outline-none focus:border-moderate cursor-pointer"
          >
            <option value="all">All Sources</option>
            <option value="cloud">Cloud</option>
            <option value="dedicated">Dedicated</option>
          </select>

          {/* Sort */}
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortOption)}
            className="bg-input border border-border text-text-primary text-xs rounded-md px-2.5 py-1.5 focus:outline-none focus:border-moderate cursor-pointer"
          >
            <option value="name">Sort: Name</option>
            <option value="cost">Sort: Cost</option>
            <option value="cpu">Sort: CPU</option>
          </select>

          {/* Search */}
          <input
            type="text"
            placeholder="Search servers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-input border border-border text-text-primary text-xs rounded-md px-3 py-1.5 w-48 placeholder:text-text-secondary focus:outline-none focus:border-moderate"
          />
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-critical/10 border border-critical/30 rounded-lg p-3 mb-4">
          <p className="text-critical text-sm">
            Failed to load servers: {error}
          </p>
        </div>
      )}

      {/* Loading state */}
      {loading && !servers && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="bg-surface border border-border rounded-lg p-4 animate-pulse"
            >
              <div className="h-4 bg-border rounded w-2/3 mb-3" />
              <div className="h-3 bg-border rounded w-1/3 mb-4" />
              <div className="h-2 bg-border rounded w-full mb-2" />
              <div className="h-2 bg-border rounded w-full mb-3" />
              <div className="h-4 bg-border rounded w-1/4" />
            </div>
          ))}
        </div>
      )}

      {/* Server grid */}
      {sorted.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {sorted.map((server: Server) => (
            <ServerCard
              key={server.id}
              server={server}
              onSelect={onSelectServer}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && sorted.length === 0 && !error && (
        <div className="flex items-center justify-center h-48 text-text-secondary text-sm">
          No servers found.
        </div>
      )}
    </section>
  );
}
