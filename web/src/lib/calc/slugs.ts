/** Calculator page slugs, kept apart from the registry so light components (like the service
 * worker registration on every page) can list them without pulling in the calculation engine.
 * registry.test.ts fails if this list and the registry ever disagree. */
export const CALCULATOR_SLUGS = [
  "dilution",
  "dehydration-deficit",
  "daily-fluid-need",
  "infusion-rate",
  "drip-rate",
  "cri",
  "flock-water-dose",
  "withdrawal-date",
] as const;
