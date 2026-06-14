import { lazy, Suspense, useEffect, useState } from "react";

// Lazy load the Leaflet components to avoid window/SSR issues
const ClientMap = lazy(() => import("./live-railway-map-client"));

interface LiveRailwayMapProps {
  showLayers?: Partial<{ trains: boolean; signals: boolean; stations: boolean; risk: boolean; incidents: boolean; weather: boolean; tracks: boolean }>;
  height?: number;
  compact?: boolean;
}

export function LiveRailwayMap(props: LiveRailwayMapProps) {
  const [mounted, setMounted] = useState(false);
  const height = props.height || 460;

  useEffect(() => {
    setMounted(true);
  }, []);

  // Show a blank dark container while loading or SSR
  const skeleton = (
    <div 
      className="relative w-full overflow-hidden rounded-lg border border-border bg-[#040810] flex items-center justify-center" 
      style={{ height }}
    >
      <div className="h-6 w-6 rounded-full border-2 border-primary border-t-transparent animate-spin" />
    </div>
  );

  if (!mounted) return skeleton;

  return (
    <Suspense fallback={skeleton}>
      <ClientMap {...props} />
    </Suspense>
  );
}
