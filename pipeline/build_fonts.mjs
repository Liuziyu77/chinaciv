// Build web/fonts/NotoSerifSC-{Regular,Bold}.woff2 — a self-hosted subset of Noto Serif SC covering exactly the
// characters this site renders (UI strings, city/province names, Almanac text: ~1,400 code points).
//
// Why: the page used to pull 思源宋体 from fonts.gstatic.com, which is unreachable from mainland China, so the
// serif look silently degraded to the system Song face. A ~350 KB local subset fixes that and removes a
// third-party request entirely.
//
// Usage:  npm i && node pipeline/build_fonts.mjs
// The full OTFs are downloaded to pipeline/vendor/ (gitignored) on first run.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import subsetFont from "subset-font";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const web = path.join(root, "web");
const vendor = path.join(root, "pipeline", "vendor");
const SRC = "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Serif/SubsetOTF/SC";

const weights = { Regular: "NotoSerifSC-Regular.woff2", Bold: "NotoSerifSC-Bold.woff2" };

// Every character that can reach a screen: source files plus the JSON the browser loads.
const files = [];
const walk = (dir) => {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name !== "fonts" && e.name !== "vendor") walk(p);
    } else if (/\.(html|js|json|css)$/.test(e.name)) files.push(p);
  }
};
walk(web);
walk(path.join(root, "docs"));

const chars = new Set(
  " 0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.,:;!?()[]{}<>/\\|+-#%&*°²³·—–…“”‘’《》、，。；：？！（）【】「」",
);
for (const f of files) {
  for (const ch of fs.readFileSync(f, "utf8")) if (ch.codePointAt(0) > 0x2000) chars.add(ch);
}
const text = [...chars].join("");
console.log(`${files.length} files → ${chars.size} unique characters`);

fs.mkdirSync(vendor, { recursive: true });
fs.mkdirSync(path.join(web, "fonts"), { recursive: true });
for (const [w, out] of Object.entries(weights)) {
  const otf = path.join(vendor, `NotoSerifSC-${w}.otf`);
  if (!fs.existsSync(otf)) {
    console.log(`downloading ${w}…`);
    execFileSync("curl", ["-fsSL", "--max-time", "300", "-o", otf, `${SRC}/NotoSerifSC-${w}.otf`], { stdio: "inherit" });
  }
  const sub = await subsetFont(fs.readFileSync(otf), text, { targetFormat: "woff2" });
  fs.writeFileSync(path.join(web, "fonts", out), sub);
  console.log(`${out}: ${(sub.length / 1024).toFixed(0)} KB`);
}
