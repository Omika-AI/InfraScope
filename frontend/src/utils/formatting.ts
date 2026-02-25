/**
 * Format a EUR cost value for display.
 */
export function formatCost(eur: number): string {
  return `\u20AC${eur.toFixed(2)}`;
}

/**
 * Format a percentage value for display.
 */
export function formatPercent(val: number): string {
  return `${val.toFixed(1)}%`;
}

/**
 * Convert an ISO date string to a relative time description.
 */
export function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;

  if (diffMs < 0) return "just now";

  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const weeks = Math.floor(days / 7);
  const months = Math.floor(days / 30);

  if (seconds < 60) return "just now";
  if (minutes === 1) return "1 minute ago";
  if (minutes < 60) return `${minutes} minutes ago`;
  if (hours === 1) return "1 hour ago";
  if (hours < 24) return `${hours} hours ago`;
  if (days === 1) return "1 day ago";
  if (days < 7) return `${days} days ago`;
  if (weeks === 1) return "1 week ago";
  if (weeks < 4) return `${weeks} weeks ago`;
  if (months === 1) return "1 month ago";
  return `${months} months ago`;
}

/**
 * Map a utilization tier to its hex color.
 */
export function tierColor(tier: string): string {
  switch (tier) {
    case "idle":
      return "#10b981";
    case "low":
      return "#f59e0b";
    case "moderate":
      return "#3b82f6";
    case "high":
      return "#f97316";
    case "critical":
      return "#ef4444";
    default:
      return "#94a3b8";
  }
}

/**
 * Map a utilization tier to a human-readable label.
 */
export function tierLabel(tier: string): string {
  switch (tier) {
    case "idle":
      return "Idle";
    case "low":
      return "Low";
    case "moderate":
      return "Moderate";
    case "high":
      return "High";
    case "critical":
      return "Critical";
    default:
      return "Unknown";
  }
}

/**
 * Map a utilization tier to its Tailwind class name for text color.
 */
export function tierTextClass(tier: string): string {
  switch (tier) {
    case "idle":
      return "text-idle";
    case "low":
      return "text-low";
    case "moderate":
      return "text-moderate";
    case "high":
      return "text-high";
    case "critical":
      return "text-critical";
    default:
      return "text-text-secondary";
  }
}

/**
 * Map a utilization tier to its Tailwind class name for background color.
 */
export function tierBgClass(tier: string): string {
  switch (tier) {
    case "idle":
      return "bg-idle";
    case "low":
      return "bg-low";
    case "moderate":
      return "bg-moderate";
    case "high":
      return "bg-high";
    case "critical":
      return "bg-critical";
    default:
      return "bg-text-secondary";
  }
}

/**
 * Format a short date for chart axis labels.
 */
export function formatShortDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/**
 * Format a full timestamp for tooltips.
 */
export function formatTimestamp(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
