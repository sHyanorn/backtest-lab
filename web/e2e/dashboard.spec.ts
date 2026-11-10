import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const DEMOS = [
  {
    key: 'ma_crossover',
    title: 'Moving-average crossover on SPY',
    verdict: 'Borderline',
  },
  {
    key: 'momentum',
    title: 'Simplified time-series momentum on SPY',
    verdict: 'Borderline',
  },
  {
    key: 'random_signal',
    title: 'Random-signal control on SPY',
    verdict: 'Fail',
  },
]

async function open(page: Page, key: string) {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  await page.goto(`#/${key}`)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  return errors
}

for (const demo of DEMOS) {
  test(`${demo.key} shows the registered report`, async ({ page }) => {
    const errors = await open(page, demo.key)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(demo.title)
    const checks = page.getByRole('region', { name: 'Overfitting checks' })
    await expect(checks.locator('.overall')).toHaveText(demo.verdict)
    await expect(
      page.getByRole('region', { name: 'Against SPY buy and hold' }),
    ).toContainText('Not part of the verdict')
    await expect(
      page.getByText('Net of 1 bp fees + 5 bps slippage per side'),
    ).toBeVisible()
    await expect(page.locator('.card')).toHaveCount(8)
    const postHoc = page.getByRole('region', { name: 'Post hoc' })
    if (demo.key === 'random_signal') await expect(postHoc).toHaveCount(0)
    else await expect(postHoc).toContainText('Not pre-registered')
    await expect(page.locator('.meta .tag')).toHaveText('Pre-registered')
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    )
    expect(overflow).toBe(0)
    expect(errors).toEqual([])
  })

  for (const scheme of ['light', 'dark'] as const) {
    test(`${demo.key} passes axe in ${scheme} mode`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme })
      await open(page, demo.key)
      await page.getByText('Table by year').click()
      const result = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze()
      expect(
        result.violations.map((v) => `${v.id}: ${v.nodes.length}`),
      ).toEqual([])
    })
  }
}

test('a details dialog opens, passes axe and closes with Escape', async ({
  page,
}) => {
  await open(page, 'ma_crossover')
  await page
    .getByRole('button', { name: 'Details of Walk-forward analysis' })
    .click()
  const dialog = page.getByRole('dialog', { name: 'Walk-forward analysis' })
  await expect(dialog).toBeVisible()
  const result = await new AxeBuilder({ page })
    .include('dialog[open]')
    .analyze()
  expect(result.violations.map((v) => v.id)).toEqual([])
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
})

test('the equity chart reads out values from the keyboard', async ({
  page,
}) => {
  await open(page, 'ma_crossover')
  const chart = page.getByRole('group', { name: /Weekly equity/ })
  await chart.focus()
  await page.keyboard.press('End')
  await expect(page.locator('.tooltip')).toContainText('Oct 30, 2026')
  await expect(page.locator('.tooltip')).toContainText('SPY$28.54')
})

test('the theme toggle switches and is remembered', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await open(page, 'momentum')
  await page.getByRole('button', { name: 'Use dark theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})

test('the static build has no live sweeps and the page fits its width', async ({
  page,
}) => {
  await open(page, 'random_signal')
  await expect(page.getByText('Static · precomputed')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Custom sweep' })).toHaveCount(0)
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  )
  expect(overflow).toBe(0)
})

test('a failed load says so instead of showing the previous search', async ({
  page,
}) => {
  await open(page, 'ma_crossover')
  await page.route(/momentum-[^/]*\.json$/, (route) => route.abort())
  await page.getByRole('link', { name: 'Momentum' }).click()
  await expect(page.getByRole('alert')).toContainText(
    'Could not load the results',
  )
  await expect(page.getByRole('heading', { level: 1 })).toHaveCount(0)
  await page.unroute(/momentum-[^/]*\.json$/)
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Simplified time-series momentum on SPY',
  )
})

test('the heat grid marks the selected setting and reads it out', async ({
  page,
}) => {
  await open(page, 'ma_crossover')
  const grid = page.getByRole('group', {
    name: /Sharpe ratio by fast and slow/,
  })
  await grid.focus()
  // The first arrow key starts at the selected setting.
  await page.keyboard.press('ArrowRight')
  await expect(page.locator('.heat .tooltip')).toContainText(
    'fast 10 · slow 200',
  )
  await expect(page.locator('.heat .tooltip')).toContainText('Sharpe 0.80')
})
