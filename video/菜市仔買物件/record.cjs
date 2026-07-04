// 用 Playwright 錄製 index.html，輸出 1920×1080 webm（靜音，音訊事後 ffmpeg mux）
// 執行：NODE_PATH=%TEMP%/cvs-render/node_modules node record.cjs
// 會輸出 renders/lead_ms.txt（錄影開始→點擊開始的毫秒數，供 mux 對齊音軌）
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// __TOTAL_MS__（由 build_timing.py 依 durations.json 回填：sum(dur)*1000 + 3000 收尾）
const TOTAL_MS = 127400;

(async () => {
  const browser = await chromium.launch({
    args: ['--autoplay-policy=no-user-gesture-required', '--mute-audio'],
  });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    recordVideo: { dir: path.join(__dirname, 'renders'), size: { width: 1920, height: 1080 } },
  });
  const tRecStart = Date.now();          // recordVideo 隨 page 建立開始
  const page = await context.newPage();
  const fileUrl = 'file:///' + path.join(__dirname, 'index.html').replace(/\\/g, '/');
  console.log('Loading:', fileUrl);
  await page.goto(fileUrl);
  await page.waitForTimeout(1800);       // 字型載入
  await page.click('#startScreen');
  const leadMs = Date.now() - tRecStart; // 影片開頭要裁掉的長度
  fs.mkdirSync(path.join(__dirname, 'renders'), { recursive: true });
  fs.writeFileSync(path.join(__dirname, 'renders', 'lead_ms.txt'), String(leadMs));
  console.log(`lead_ms = ${leadMs}, recording ${TOTAL_MS / 1000}s ...`);
  await page.waitForTimeout(TOTAL_MS);
  await context.close();
  await browser.close();
  console.log('Done. webm in renders/');
})();
