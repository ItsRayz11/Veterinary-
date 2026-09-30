import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "VetRef: Veterinary Reference",
    short_name: "VetRef",
    description:
      "Veterinary drug reference, brands, calculators and education for veterinary professionals.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f7f8fa",
    theme_color: "#0b6e6e",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    shortcuts: [
      { name: "Calculators", url: "/calculators" },
      { name: "Search drugs", url: "/search" },
      { name: "Interaction checker", url: "/interactions" },
      { name: "Study", url: "/study" },
    ],
  };
}
