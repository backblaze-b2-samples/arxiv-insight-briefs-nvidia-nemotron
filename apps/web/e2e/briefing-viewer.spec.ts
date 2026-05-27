import { test, expect } from "@playwright/test";

// Regression guard for the `BriefingViewer` markdown renderer.
//
// The brief synthesis prompt regularly emits ordered lists. The original
// hand-rolled renderer silently dropped them (no `^\d+\. ` rule); the
// `react-markdown`-backed renderer fixes that. This e2e asserts the
// rendered tree contains a real <ol> with the expected items.
test("briefing viewer renders ordered lists and citation chips", async ({ page }) => {
  await page.goto("/design");

  const sample = page.getByTestId("design-briefing-sample");
  await expect(sample).toBeVisible();

  // Ordered list — three items in the fixture.
  const orderedList = sample.locator("ol");
  await expect(orderedList).toHaveCount(1);
  await expect(orderedList.locator("li")).toHaveCount(3);

  // Citation chip — server emits [arxiv:ID](presigned-url-for-papers/ID.pdf);
  // the custom <a> override detects the `/papers/.../*.pdf` href shape (set
  // by the synthesis citation rewriter) and applies the chip styling. We
  // assert against the href detector — not the label — because react-markdown
  // v9 passes inline children (e.g. wrapping <code>) as React nodes, not a
  // plain string. Regression: the previous label-based check silently fell
  // through to the plain-link branch.
  const citation = sample.getByRole("link", { name: /^arxiv:/ });
  await expect(citation).toBeVisible();
  await expect(citation).toHaveAttribute("target", "_blank");
  // Chip-class signature: rounded mono pill, no underline.
  await expect(citation).toHaveClass(/rounded/);
  await expect(citation).toHaveClass(/font-mono/);
  await expect(citation).toHaveClass(/no-underline/);
});
