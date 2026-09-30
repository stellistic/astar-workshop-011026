import type { Page } from "playwright";

export type Box = { x: number; y: number; width: number; height: number };

const OVERLAY_ID = "__capture_overlay__";
const CURSOR_ID = "__capture_cursor__";

/** Draws numbered red call-out boxes over the given viewport rectangles. */
export async function drawHighlights(page: Page, boxes: Box[], pad = 6): Promise<void> {
  await page.evaluate(
    ({ boxes, pad, id }) => {
      document.getElementById(id)?.remove();
      const layer = document.createElement("div");
      layer.id = id;
      Object.assign(layer.style, {
        position: "fixed",
        inset: "0",
        pointerEvents: "none",
        zIndex: "2147483647",
      });
      boxes.forEach((b, i) => {
        const r = document.createElement("div");
        Object.assign(r.style, {
          position: "fixed",
          left: `${b.x - pad}px`,
          top: `${b.y - pad}px`,
          width: `${b.width + pad * 2}px`,
          height: `${b.height + pad * 2}px`,
          border: "3px solid #E3008C",
          borderRadius: "6px",
          boxShadow: "0 0 0 3px rgba(227,0,140,0.25)",
        });
        layer.appendChild(r);
        if (boxes.length > 1) {
          const badge = document.createElement("div");
          badge.textContent = String(i + 1);
          Object.assign(badge.style, {
            position: "fixed",
            left: `${b.x - pad - 12}px`,
            top: `${b.y - pad - 12}px`,
            width: "24px",
            height: "24px",
            borderRadius: "12px",
            background: "#E3008C",
            color: "white",
            font: "bold 13px Segoe UI, sans-serif",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          });
          layer.appendChild(badge);
        }
      });
      document.body.appendChild(layer);
    },
    { boxes, pad, id: OVERLAY_ID },
  );
}

export async function clearHighlights(page: Page): Promise<void> {
  await page.evaluate((id) => document.getElementById(id)?.remove(), OVERLAY_ID).catch(() => undefined);
}

/** Moves a visible cursor dot to a point so recordings show where the click lands. */
export async function showCursor(page: Page, x: number, y: number, dwellMs = 450): Promise<void> {
  await page
    .evaluate(
      ({ x, y, id }) => {
        let dot = document.getElementById(id);
        if (!dot) {
          dot = document.createElement("div");
          dot.id = id;
          Object.assign(dot.style, {
            position: "fixed",
            width: "22px",
            height: "22px",
            marginLeft: "-11px",
            marginTop: "-11px",
            borderRadius: "11px",
            background: "rgba(227,0,140,0.35)",
            border: "2px solid #E3008C",
            pointerEvents: "none",
            zIndex: "2147483647",
            transition: "left 350ms ease, top 350ms ease",
            left: `${x}px`,
            top: `${y}px`,
          });
          document.body.appendChild(dot);
        }
        dot.style.left = `${x}px`;
        dot.style.top = `${y}px`;
      },
      { x, y, id: CURSOR_ID },
    )
    .catch(() => undefined);
  await page.waitForTimeout(dwellMs);
}

export async function hideCursor(page: Page): Promise<void> {
  await page.evaluate((id) => document.getElementById(id)?.remove(), CURSOR_ID).catch(() => undefined);
}
