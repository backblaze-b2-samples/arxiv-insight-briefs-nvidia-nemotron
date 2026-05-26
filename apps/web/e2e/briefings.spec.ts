import { test, expect } from "@playwright/test";

// Smoke test only — the form should render and accept text. Submitting
// is intentionally not exercised here because that requires a live API
// + B2 + (optionally) NVIDIA. Run `pnpm dev` with real credentials when
// you want to validate the full path.
test("new-brief form renders", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "New brief" })).toBeVisible();
  await expect(page.getByPlaceholder(/research/i)).toBeVisible();
});
