import { useState } from "react";
import Dashboard from "./components/Dashboard";
import ServerDetail from "./components/ServerDetail";

export default function App() {
  const [selectedServerId, setSelectedServerId] = useState<number | null>(null);

  return (
    <div className="min-h-screen bg-background text-text-primary">
      <Dashboard onSelectServer={setSelectedServerId} />

      {selectedServerId !== null && (
        <ServerDetail
          serverId={selectedServerId}
          onClose={() => setSelectedServerId(null)}
        />
      )}
    </div>
  );
}
