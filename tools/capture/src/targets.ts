import { z } from "zod";
import type { FrameLocator, Locator, Page } from "playwright";

type AriaRole = Parameters<Page["getByRole"]>[0];

export const targetSchema = z
  .object({
    role: z.string().optional(),
    name: z.string().optional(),
    text: z.string().optional(),
    css: z.string().optional(),
    label: z.string().optional(),
    placeholder: z.string().optional(),
    title: z.string().optional(),
    testId: z.string().optional(),
    exact: z.boolean().optional(),
    hasText: z.string().optional(),
    nth: z.number().int().optional(),
    frame: z.union([z.string(), z.array(z.string())]).optional(),
    within: z.string().optional(),
  })
  .refine(
    (t) => [t.role, t.text, t.css, t.label, t.placeholder, t.title, t.testId].some((v) => v !== undefined),
    { message: "target needs one of role|text|css|label|placeholder|title|testId" },
  );

export type Target = z.infer<typeof targetSchema>;

type Root = Page | FrameLocator | Locator;

function frameRoot(page: Page, frame: Target["frame"]): Page | FrameLocator {
  if (frame === undefined) return page;
  const chain = Array.isArray(frame) ? frame : [frame];
  let root: Page | FrameLocator = page;
  for (const css of chain) root = root.frameLocator(css);
  return root;
}

export function resolveTarget(page: Page, target: Target): Locator {
  let root: Root = frameRoot(page, target.frame);
  if (target.within !== undefined) root = root.locator(target.within);
  const exact = target.exact ?? false;
  let loc: Locator;
  if (target.role !== undefined) {
    loc = root.getByRole(target.role as AriaRole, target.name !== undefined ? { name: target.name, exact } : {});
  } else if (target.text !== undefined) {
    loc = root.getByText(target.text, { exact });
  } else if (target.label !== undefined) {
    loc = root.getByLabel(target.label, { exact });
  } else if (target.placeholder !== undefined) {
    loc = root.getByPlaceholder(target.placeholder, { exact });
  } else if (target.title !== undefined) {
    loc = root.getByTitle(target.title, { exact });
  } else if (target.testId !== undefined) {
    loc = root.getByTestId(target.testId);
  } else {
    loc = root.locator(target.css ?? "body");
  }
  if (target.hasText !== undefined) loc = loc.filter({ hasText: target.hasText });
  if (target.nth !== undefined) loc = loc.nth(target.nth);
  return loc;
}
