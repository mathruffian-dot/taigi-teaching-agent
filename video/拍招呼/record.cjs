// 用 Playwright 錄製 index.html，輸出 1920×1080 webm（靜音，音訊事後用 ffmpeg mux）
// Playwright 依 Hyperframe 慣例裝在 %TEMP%/cvs-render，執行時用 NODE_PATH 指向它：
//   NODE_PATH=%TEMP%/cvs-render/node_modules node record.cjs
const { chromium } = require('playwright');
const path = require('path');

// 9 頁 dur 總和 = 136s，加緩衝
const TOTAL_MS = 140000;

(async () => {
  const browser = await chromium.launch({
    args: ['--autoplay-policy=no-user-gesture-required', '--mute-audio'],
  });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    recordVideo: { dir: path.join(__dirname, 'renders'), size: { width: 1920, height: 1080 } },
  });
  const page = await context.newPage();
  const fileUrl = 'file:///' + path.join(__dirname, 'index.html').replace(/\\/g, '/');
  console.log('Loading:', fileUrl);
  await page.goto(fileUrl);
  await page.waitForTimeout(1500);   // 字型載入
  await page.click('#startScreen');
  console.log(`Recording ${TOTAL_MS / 1000}s ...`);
  await page.waitForTimeout(TOTAL_MS);
  await context.close();
  await browser.close();
  console.log('Done. webm in renders/');
})();
