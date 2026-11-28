import { ImageResponse } from "next/og";

export const alt = "VetRef: veterinary drug reference, brands, calculators and education";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Colours from the site's tokens (globals.css): flat page, ink text, one teal accent.
const BG = "#f6f7f7";
const TEXT = "#121a1c";
const TEXT_2 = "#3e4b51";
const PRIMARY = "#0b6e6e";
const OK = "#1b7a3d";
const WARN = "#8a5a00";

export default function OpengraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: 80,
        background: BG,
        color: TEXT,
        borderTop: `12px solid ${PRIMARY}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <svg width="64" height="64" viewBox="0 0 22 22">
          <circle cx="11" cy="11" r="9.25" fill="none" stroke={PRIMARY} strokeWidth="1.5" />
          <circle cx="11" cy="11" r="4" fill={PRIMARY} />
        </svg>
        <div style={{ fontSize: 52, fontWeight: 600 }}>VetRef</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ fontSize: 84, lineHeight: 1.05, letterSpacing: -2 }}>
          Veterinary drug reference
        </div>
        <div style={{ fontSize: 36, color: TEXT_2, maxWidth: 900 }}>
          Generics, brands and manufacturers by country, with the source and review status of every
          clinical statement
        </div>
      </div>
      <div style={{ display: "flex", gap: 40, fontSize: 28, color: TEXT_2 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 18, height: 18, borderRadius: 9, background: OK }} />
          Clinically reviewed
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 18, height: 18, borderRadius: 9, border: `3px solid ${WARN}` }} />
          Imported, not yet reviewed
        </div>
      </div>
    </div>,
    size,
  );
}
