import { useState, useEffect } from "react";
import { timeAgo } from "@/utils/formatting";
import CostOverview from "./CostOverview";
import Recommendations from "./Recommendations";
import ServerGrid from "./ServerGrid";

interface DashboardProps {
  onSelectServer: (id: number) => void;
}

export default function Dashboard({ onSelectServer }: DashboardProps) {
  const [lastSync, setLastSync] = useState<string>(new Date().toISOString());

  // Update the "last sync" timestamp every time the component renders
  // and refresh the display every 30 seconds
  useEffect(() => {
    setLastSync(new Date().toISOString());
    const interval = setInterval(() => {
      setLastSync(new Date().toISOString());
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-md border-b border-border">
        <div className="max-w-[1600px] mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Logo / Title */}
            <div className="flex items-center gap-2">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="w-6 h-6 text-moderate"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
                />
              </svg>
              <h1 className="text-text-primary text-lg font-bold tracking-tight">
                InfraScope
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Last sync */}
            <span className="text-text-secondary text-xs">
              Last sync: {timeAgo(lastSync)}
            </span>

            {/* Settings icon */}
            <button
              type="button"
              className="text-text-secondary hover:text-text-primary transition-colors p-1 cursor-pointer"
              aria-label="Settings"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-[1600px] mx-auto px-6 py-6 space-y-6">
        <CostOverview />
        <Recommendations />
        <ServerGrid onSelectServer={onSelectServer} />
      </main>
    </div>
  );
}
