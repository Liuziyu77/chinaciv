// Build web/data/pinyin.json: full pinyin and pinyin initials for every city and province, so the top-bar
// search accepts "shenzhen" and "sz" as well as 深圳. Needs `npm i pinyin-pro` (build-time only; the site has
// no runtime dependency).
import { pinyin } from "pinyin-pro";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataDir = path.join(root, "web", "data");
const read = (name) => JSON.parse(fs.readFileSync(path.join(dataDir, name), "utf8"));
const norm = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "");
const mark = (raw) => ({
  py: norm(pinyin(raw, { toneType: "none", type: "array" }).join("")),
  pyi: norm(pinyin(raw, { pattern: "first", toneType: "none", type: "array" }).join("")),
});

const cities = read("cities.json");
const world = read("world.json");
const out = { cities: {}, states: {} };
for (const c of cities) out.cities[c.id] = mark(c.name);
for (const s of world.states) out.states[s.fips] = mark(s.name);
fs.writeFileSync(path.join(dataDir, "pinyin.json"), JSON.stringify(out));
console.log(`pinyin: ${Object.keys(out.cities).length} cities, ${Object.keys(out.states).length} provinces`);
