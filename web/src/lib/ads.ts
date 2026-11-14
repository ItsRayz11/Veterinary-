/** Advertising configuration. Everything is OFF unless an owner sets both variables on the server:
 *  ADS_ENABLED=true and ADSENSE_CLIENT=ca-pub-<digits>. Read at build/start time (redeploy to change). */

export interface AdsConfig {
  enabled: boolean;
  client: string;
  /** Slot ids keyed by zone, from ADSENSE_SLOT_<ZONE> */
  slots: Partial<Record<AdZone, string>>;
}

/** Ads may appear only in these zones. There is deliberately no "clinical" or "regulatory"
 *  zone: doses, withdrawal periods, interactions, registrations and calculators never get ads. */
export const AD_ZONES = ["directory", "education", "blog", "jobs"] as const;
export type AdZone = (typeof AD_ZONES)[number];

const CLIENT = /^ca-pub-\d{8,20}$/;
const SLOT = /^\d{6,20}$/;

export function adsConfig(env: Record<string, string | undefined> = process.env): AdsConfig {
  const client = env.ADSENSE_CLIENT ?? "";
  const enabled = env.ADS_ENABLED === "true" && CLIENT.test(client);
  const slots: AdsConfig["slots"] = {};
  for (const zone of AD_ZONES) {
    const id = env[`ADSENSE_SLOT_${zone.toUpperCase()}`] ?? "";
    if (SLOT.test(id)) slots[zone] = id;
  }
  return { enabled, client: enabled ? client : "", slots: enabled ? slots : {} };
}

/** Content for /ads.txt, or null when no publisher id is configured. */
export function adsTxt(env: Record<string, string | undefined> = process.env): string | null {
  const client = env.ADSENSE_CLIENT ?? "";
  if (!CLIENT.test(client)) return null;
  return `google.com, ${client.replace("ca-", "")}, DIRECT, f08c47fec0942fa0\n`;
}

/** Extra CSP sources, added only when ads are enabled. */
export const AD_CSP = {
  script: ["https://pagead2.googlesyndication.com", "https://www.googletagservices.com"],
  frame: [
    "https://googleads.g.doubleclick.net",
    "https://tpc.googlesyndication.com",
    "https://pagead2.googlesyndication.com",
  ],
  img: ["https://pagead2.googlesyndication.com", "https://googleads.g.doubleclick.net"],
  connect: ["https://pagead2.googlesyndication.com", "https://googleads.g.doubleclick.net"],
} as const;
