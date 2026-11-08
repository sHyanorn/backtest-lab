// Captures the README screenshot from a running build: npm run build && npm run preview,
// then node scripts/screenshot.mjs [url]
import { chromium } from '@playwright/test'

const url = process.argv[2] ?? 'http://localhost:4173/'
const out = new URL('../../docs/images/dashboard.png', import.meta.url)

const browser = await chromium.launch()
const page = await browser.newPage({
  viewport: { width: 1200, height: 1200 },
  deviceScaleFactor: 1.5,
  colorScheme: 'light',
})
await page.goto(`${url}#/ma_crossover`)
await page.getByRole('heading', { level: 1 }).waitFor()
await page.waitForTimeout(300)
// From the header to the end of the equity chart
const chart = await page
  .getByRole('region', { name: 'Equity and drawdown' })
  .boundingBox()
await page.screenshot({
  path: out.pathname,
  clip: {
    x: 0,
    y: 0,
    width: 1200,
    height: Math.ceil(chart.y + chart.height + 24),
  },
})
await browser.close()
console.log(`wrote ${out.pathname}`)
