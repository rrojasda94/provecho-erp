import { test } from "@playwright/test";
test("shot", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 700 });
  await page.goto("/");
  await page.locator("footer").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "C:/Users/renat/AppData/Local/Temp/shot-footer.png" });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "C:/Users/renat/AppData/Local/Temp/shot-head.png", clip: { x: 0, y: 0, width: 1100, height: 120 } });
});
