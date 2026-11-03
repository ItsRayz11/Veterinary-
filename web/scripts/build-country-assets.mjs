/**
 * Builds the static country assets in public/:
 *   flags/<iso2>.svg  copied from the `flag-icons` package (MIT; the flags are public symbols)
 *   maps/<iso2>.svg   outline drawn from Natural Earth 1:50m boundaries via `world-atlas` (public domain)
 *
 * Run from web/:  node scripts/build-country-assets.mjs
 * Sources and licences are listed on the /credits page.
 */
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { geoAlbersUsa, geoMercator, geoPath } from "d3-geo";
import { feature } from "topojson-client";

const require = createRequire(import.meta.url);
const iso = require("i18n-iso-countries");
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const flagSrc = join(root, "node_modules/flag-icons/flags/4x3");
const flagOut = join(root, "public/flags");
const mapOut = join(root, "public/maps");
mkdirSync(flagOut, { recursive: true });
mkdirSync(mapOut, { recursive: true });

let flags = 0;
for (const f of readdirSync(flagSrc)) {
  if (!f.endsWith(".svg")) continue;
  copyFileSync(join(flagSrc, f), join(flagOut, f));
  flags++;
}

const topo = JSON.parse(
  readFileSync(join(root, "node_modules/world-atlas/countries-50m.json"), "utf8"),
);
const W = 400;
const H = 300;
let maps = 0;
for (const f of feature(topo, topo.objects.countries).features) {
  const alpha2 = iso.numericToAlpha2(String(f.id).padStart(3, "0"));
  if (!alpha2) continue;
  const code = alpha2.toLowerCase();
  const projection = (code === "us" ? geoAlbersUsa() : geoMercator()).fitExtent(
    [
      [12, 12],
      [W - 12, H - 12],
    ],
    f,
  );
  const d = geoPath(projection).digits(1)(f);
  if (!d) continue;
  const name = (iso.getName(alpha2, "en") ?? alpha2).replace(/&/g, "&amp;");
  writeFileSync(
    join(mapOut, `${code}.svg`),
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Outline map of ${name}"><path d="${d}" fill="#3a9a96" fill-opacity=".85" stroke="#0b6e6e" stroke-width="1" stroke-linejoin="round"/></svg>\n`,
  );
  maps++;
}
console.log(`flags: ${flags}, maps: ${maps}`);
if (!existsSync(join(mapOut, "in.svg"))) throw new Error("India map missing");
