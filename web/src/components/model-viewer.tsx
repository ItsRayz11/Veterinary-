"use client";

import { createElement, useEffect, useState } from "react";

/**
 * Interactive 3D preview. The viewer library is loaded only when this component mounts, and the
 * static fallback image (or a text notice) shows if WebGL, the model or the library is missing.
 */
export function ModelViewer({
  src,
  alt,
  fallbackImage,
}: {
  src: string;
  alt: string;
  fallbackImage?: string;
}) {
  const [ready, setReady] = useState<"loading" | "ok" | "failed">("loading");
  useEffect(() => {
    let live = true;
    import("@google/model-viewer")
      .then(() => live && setReady("ok"))
      .catch(() => live && setReady("failed"));
    return () => {
      live = false;
    };
  }, []);

  if (ready === "failed")
    return fallbackImage ? (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={fallbackImage} alt={alt} className="w-full rounded-lg" />
    ) : (
      <p className="text-sm text-muted">The 3D preview is not available in this browser.</p>
    );
  if (ready === "loading")
    return <div className="h-72 w-full animate-pulse rounded-lg bg-surface-2" />;
  return createElement("model-viewer", {
    src,
    alt,
    "camera-controls": "",
    "touch-action": "pan-y",
    "auto-rotate": "",
    "shadow-intensity": "1",
    poster: fallbackImage,
    style: { width: "100%", height: "18rem", borderRadius: "0.5rem" },
  });
}
