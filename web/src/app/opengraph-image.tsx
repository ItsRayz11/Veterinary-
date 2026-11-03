import { ImageResponse } from "next/og";

export const alt = "VetRef: veterinary drug reference, brands, calculators and education";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: 80,
        background: "linear-gradient(135deg, #0b6e6e, #0e1418)",
        color: "white",
      }}
    >
      <div style={{ fontSize: 120, fontWeight: 700 }}>VetRef</div>
      <div style={{ fontSize: 44, marginTop: 24, opacity: 0.9 }}>
        Veterinary drug reference, brands, calculators and education
      </div>
    </div>,
    size,
  );
}
