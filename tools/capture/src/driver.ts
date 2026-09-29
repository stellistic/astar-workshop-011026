import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { mkdir } from "node:fs/promises";
import { dirname, isAbsolute, join } from "node:path";
import { chromium, type BrowserContext, type Page } from "playwright";
import { loadConfig, type DriverConfig } from "./config.js";
import { commandSchema, type Command } from "./commands.js";
import { resolveTarget } from "./targets.js";
import { clearHighlights, drawHighlights, hideCursor, showCursor, type Box } from "./overlay.js";

type Result = Record<string, unknown>;

class Driver {
  private page: Page | undefined;

  constructor(
    private readonly context: BrowserContext,
    private readonly config: DriverConfig,
  ) {
    this.page = context.pages()[0];
  }

  private current(): Page {
    const open = this.context.pages();
    if (this.page === undefined || this.page.isClosed()) this.page = open[open.length - 1];
    if (this.page === undefined) throw new Error("no open page; send {op:'newPage'}");
    return this.page;
  }

  private out(path: string): string {
    return isAbsolute(path) ? path : join(this.config.outputDir, path);
  }

  async run(cmd: Command): Promise<Result> {
    switch (cmd.op) {
      case "goto": {
        const page = this.current();
        await page.goto(cmd.url, { waitUntil: cmd.waitUntil ?? "domcontentloaded" });
        return { url: page.url(), title: await page.title() };
      }
      case "newPage": {
        this.page = await this.context.newPage();
        return { pages: this.context.pages().length };
      }
      case "closePage": {
        const page = this.current();
        const video = page.video();
        await page.close();
        let saved: string | undefined;
        if (video !== null && cmd.saveVideoAs !== undefined) {
          saved = this.out(cmd.saveVideoAs);
          await mkdir(dirname(saved), { recursive: true });
          await video.saveAs(saved);
        }
        this.page = undefined;
        return { closed: true, video: saved ?? null };
      }
      case "usePage": {
        const page = this.context.pages()[cmd.index];
        if (page === undefined) throw new Error(`no page at index ${cmd.index}`);
        this.page = page;
        await page.bringToFront();
        return { url: page.url() };
      }
      case "info": {
        const page = this.current();
        const pages = await Promise.all(this.context.pages().map(async (p, i) => ({ i, url: p.url(), title: await p.title().catch(() => "") })));
        return { url: page.url(), title: await page.title(), pages };
      }
      case "frames": {
        return { frames: this.current().frames().map((f) => ({ name: f.name(), url: f.url() })) };
      }
      case "click": {
        const page = this.current();
        const loc = resolveTarget(page, cmd.target);
        await loc.waitFor({ state: "visible", timeout: cmd.timeout ?? 20000 });
        if (cmd.showCursor !== false) {
          const box = await loc.boundingBox();
          if (box !== null) await showCursor(page, box.x + (cmd.position?.x ?? box.width / 2), box.y + (cmd.position?.y ?? box.height / 2));
        }
        const opts = { button: cmd.button, force: cmd.force, timeout: cmd.timeout ?? 20000, position: cmd.position, modifiers: cmd.modifiers };
        if (cmd.double === true) await loc.dblclick(opts);
        else await loc.click(opts);
        return { clicked: true };
      }
      case "clickXY": {
        const page = this.current();
        await showCursor(page, cmd.x, cmd.y);
        if (cmd.double === true) await page.mouse.dblclick(cmd.x, cmd.y);
        else await page.mouse.click(cmd.x, cmd.y);
        return { clicked: true };
      }
      case "hover": {
        const page = this.current();
        const loc = resolveTarget(page, cmd.target);
        await loc.hover({ timeout: cmd.timeout ?? 20000 });
        return { hovered: true };
      }
      case "fill": {
        const loc = resolveTarget(this.current(), cmd.target);
        await loc.fill(cmd.value, { timeout: cmd.timeout ?? 20000 });
        return { filled: true };
      }
      case "type": {
        await this.current().keyboard.type(cmd.text, { delay: cmd.delay ?? 15 });
        return { typed: cmd.text.length };
      }
      case "press": {
        await this.current().keyboard.press(cmd.key);
        return { pressed: cmd.key };
      }
      case "check": {
        const loc = resolveTarget(this.current(), cmd.target);
        await loc.setChecked(cmd.checked);
        return { checked: cmd.checked };
      }
      case "select": {
        const loc = resolveTarget(this.current(), cmd.target);
        return { selected: await loc.selectOption(cmd.value) };
      }
      case "upload": {
        const page = this.current();
        if (cmd.input !== undefined) {
          await resolveTarget(page, cmd.input).setInputFiles(cmd.files);
        } else if (cmd.trigger !== undefined) {
          const chooser = page.waitForEvent("filechooser", { timeout: 20000 });
          await resolveTarget(page, cmd.trigger).click();
          await (await chooser).setFiles(cmd.files);
        } else {
          throw new Error("upload needs input or trigger");
        }
        return { uploaded: cmd.files.length };
      }
      case "shot": {
        const page = this.current();
        await hideCursor(page);
        const boxes: Box[] = [...(cmd.boxes ?? [])];
        for (const target of cmd.highlight ?? []) {
          const box = await resolveTarget(page, target).first().boundingBox();
          if (box === null) throw new Error(`highlight target not visible: ${JSON.stringify(target)}`);
          boxes.push(box);
        }
        if (boxes.length > 0) await drawHighlights(page, boxes, cmd.pad ?? 6);
        const path = this.out(cmd.path);
        await mkdir(dirname(path), { recursive: true });
        try {
          if (cmd.element !== undefined) await resolveTarget(page, cmd.element).first().screenshot({ path });
          else await page.screenshot({ path, fullPage: cmd.fullPage ?? false, ...(cmd.clip !== undefined ? { clip: cmd.clip } : {}) });
        } finally {
          await clearHighlights(page);
        }
        return { path, highlighted: boxes.length };
      }
      case "aria": {
        const page = this.current();
        const loc = cmd.target !== undefined ? resolveTarget(page, cmd.target).first() : page.locator("body");
        let snap = await loc.ariaSnapshot({ timeout: 20000 });
        if (cmd.grep !== undefined) {
          const re = new RegExp(cmd.grep, "i");
          snap = snap.split("\n").filter((l) => re.test(l)).join("\n");
        }
        const max = cmd.max ?? 12000;
        return { aria: snap.length > max ? `${snap.slice(0, max)}\n…[truncated ${snap.length - max} chars]` : snap };
      }
      case "count": {
        return { count: await resolveTarget(this.current(), cmd.target).count() };
      }
      case "box": {
        return { box: await resolveTarget(this.current(), cmd.target).first().boundingBox() };
      }
      case "text": {
        const text = await resolveTarget(this.current(), cmd.target).first().innerText({ timeout: 20000 });
        const max = cmd.max ?? 8000;
        return { text: text.length > max ? `${text.slice(0, max)}…` : text };
      }
      case "eval": {
        const page = this.current();
        const frame = cmd.frameUrlContains !== undefined ? page.frames().find((f) => f.url().includes(cmd.frameUrlContains ?? "")) : page.mainFrame();
        if (frame === undefined) throw new Error("frame not found");
        return { value: await frame.evaluate(cmd.js) };
      }
      case "wait": {
        const page = this.current();
        if (cmd.target !== undefined) {
          await resolveTarget(page, cmd.target).first().waitFor({ state: cmd.state ?? "visible", timeout: cmd.timeout ?? 60000 });
        }
        if (cmd.ms !== undefined) await page.waitForTimeout(cmd.ms);
        return { waited: true };
      }
      case "scroll": {
        const page = this.current();
        if (cmd.target !== undefined) await resolveTarget(page, cmd.target).first().scrollIntoViewIfNeeded();
        else await page.mouse.wheel(0, cmd.dy ?? 400);
        return { scrolled: true };
      }
      case "resize": {
        await this.current().setViewportSize({ width: cmd.width, height: cmd.height });
        return { resized: true };
      }
    }
  }
}

async function readBody(req: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString("utf8");
}

function send(res: ServerResponse, status: number, body: Result): void {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

async function main(): Promise<void> {
  const config = loadConfig(process.env);
  await mkdir(config.outputDir, { recursive: true });
  const context = await chromium.launchPersistentContext(config.profileDir, {
    headless: false,
    ...(config.channel !== "chromium" ? { channel: config.channel } : {}),
    viewport: config.viewport,
    deviceScaleFactor: 1,
    locale: "en-US",
    timezoneId: "Asia/Singapore",
    acceptDownloads: true,
    ...(config.recordVideo ? { recordVideo: { dir: join(config.outputDir, "_video_raw"), size: config.viewport } } : {}),
  });
  const driver = new Driver(context, config);
  let queue: Promise<unknown> = Promise.resolve();

  const server = createServer((req, res) => {
    if (req.method !== "POST" || req.url !== "/cmd") {
      send(res, 404, { ok: false, error: "POST /cmd only" });
      return;
    }
    queue = queue.then(async () => {
      try {
        const parsed = commandSchema.safeParse(JSON.parse(await readBody(req)));
        if (!parsed.success) {
          send(res, 400, { ok: false, error: parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ") });
          return;
        }
        send(res, 200, { ok: true, ...(await driver.run(parsed.data)) });
      } catch (error) {
        send(res, 500, { ok: false, error: error instanceof Error ? error.message.split("\n").slice(0, 8).join("\n") : String(error) });
      }
    });
  });
  server.listen(config.port, "127.0.0.1", () => {
    process.stdout.write(`capture driver listening on http://127.0.0.1:${config.port}/cmd\n`);
  });
  context.on("close", () => server.close());
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.stack ?? error.message : String(error)}\n`);
  process.exit(1);
});
