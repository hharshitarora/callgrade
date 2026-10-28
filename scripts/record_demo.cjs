// Records the demo page playing itself (index.html?auto) into site/demo.mp4
// and a short docs/demo.gif for the README. Needs Playwright on NODE_PATH and
// the site served locally:
//
//   python -m http.server 8771 --directory site
//   NODE_PATH=/path/with/node_modules node scripts/record_demo.cjs
//
// The webm to mp4 and gif steps need a full ffmpeg (Playwright's own build has
// no H.264 or GIF encoder): `pip install imageio-ffmpeg` into the venv, or set
// FFMPEG to any ffmpeg binary. Set WEBM to convert an existing recording.
const { chromium } = require("playwright");
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const URL = process.env.DEMO_URL || "http://localhost:8771/index.html?auto";
const size = { width: 1280, height: 860 };

async function record() {
  const tmp = fs.mkdtempSync(path.join(require("os").tmpdir(), "callgrade-demo-"));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: size, colorScheme: "light", recordVideo: { dir: tmp, size } });
  const page = await ctx.newPage();
  await page.goto(URL);
  // the page sets window.demoDone when the auto run finishes
  await page.waitForFunction(() => window.demoDone === true, null, { timeout: 180000 });
  await page.waitForTimeout(2000);
  const video = page.video();
  await ctx.close();
  const webm = await video.path();
  await browser.close();
  return webm;
}

function findFfmpeg() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  for (const py of [path.join(ROOT, ".venv", "Scripts", "python.exe"), path.join(ROOT, ".venv", "bin", "python"), "python"]) {
    try { return execFileSync(py, ["-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"], { encoding: "utf-8" }).trim(); } catch {}
  }
  throw new Error("no ffmpeg: pip install imageio-ffmpeg, or set FFMPEG");
}

(async () => {
  const webm = process.env.WEBM || await record();
  const ffmpeg = findFfmpeg();
  const mp4 = path.join(ROOT, "site", "demo.mp4");
  const gif = path.join(ROOT, "docs", "demo.gif");
  fs.mkdirSync(path.dirname(gif), { recursive: true });
  execFileSync(ffmpeg, ["-y", "-i", webm, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", "-movflags", "+faststart", mp4], { stdio: "inherit" });
  // GIF: the first call only, 640px wide, 8 fps, with a palette so text stays readable
  const gifSeconds = process.env.GIF_SECONDS || "26";
  execFileSync(ffmpeg, ["-y", "-ss", "2", "-t", gifSeconds, "-i", webm, "-vf", "fps=8,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4", gif], { stdio: "inherit" });
  const mb = (f) => (fs.statSync(f).size / 1e6).toFixed(1) + "MB";
  console.log(`wrote ${mp4} (${mb(mp4)}) and ${gif} (${mb(gif)})`);
})();
