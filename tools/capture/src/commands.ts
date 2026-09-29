import { z } from "zod";
import { targetSchema } from "./targets.js";

const t = targetSchema;

export const commandSchema = z.discriminatedUnion("op", [
  z.object({ op: z.literal("goto"), url: z.string().url(), waitUntil: z.enum(["load", "domcontentloaded", "networkidle", "commit"]).optional() }),
  z.object({ op: z.literal("newPage"), label: z.string().min(1).optional() }),
  z.object({ op: z.literal("closePage"), saveVideoAs: z.string().optional() }),
  z.object({ op: z.literal("info") }),
  z.object({ op: z.literal("usePage"), index: z.number().int().nonnegative() }),
  z.object({ op: z.literal("frames") }),
  z.object({
    op: z.literal("click"),
    target: t,
    button: z.enum(["left", "right", "middle"]).optional(),
    double: z.boolean().optional(),
    force: z.boolean().optional(),
    timeout: z.number().int().positive().optional(),
    showCursor: z.boolean().optional(),
    position: z.object({ x: z.number(), y: z.number() }).optional(),
  }),
  z.object({ op: z.literal("clickXY"), x: z.number(), y: z.number(), double: z.boolean().optional() }),
  z.object({ op: z.literal("hover"), target: t, timeout: z.number().int().positive().optional() }),
  z.object({ op: z.literal("fill"), target: t, value: z.string(), timeout: z.number().int().positive().optional() }),
  z.object({ op: z.literal("type"), text: z.string(), delay: z.number().int().nonnegative().optional() }),
  z.object({ op: z.literal("press"), key: z.string().min(1) }),
  z.object({ op: z.literal("check"), target: t, checked: z.boolean().default(true) }),
  z.object({ op: z.literal("select"), target: t, value: z.union([z.string(), z.array(z.string())]) }),
  z.object({
    op: z.literal("upload"),
    files: z.array(z.string().min(1)).min(1),
    input: t.optional(),
    trigger: t.optional(),
  }),
  z.object({
    op: z.literal("shot"),
    path: z.string().min(1),
    highlight: z.array(t).optional(),
    boxes: z.array(z.object({ x: z.number(), y: z.number(), width: z.number(), height: z.number() })).optional(),
    element: t.optional(),
    fullPage: z.boolean().optional(),
    pad: z.number().nonnegative().optional(),
    clip: z.object({ x: z.number(), y: z.number(), width: z.number().positive(), height: z.number().positive() }).optional(),
  }),
  z.object({ op: z.literal("aria"), target: t.optional(), grep: z.string().optional(), max: z.number().int().positive().optional() }),
  z.object({ op: z.literal("count"), target: t }),
  z.object({ op: z.literal("box"), target: t }),
  z.object({ op: z.literal("text"), target: t, max: z.number().int().positive().optional() }),
  z.object({ op: z.literal("eval"), js: z.string().min(1), frameUrlContains: z.string().optional() }),
  z.object({ op: z.literal("wait"), ms: z.number().int().nonnegative().optional(), target: t.optional(), state: z.enum(["visible", "hidden", "attached", "detached"]).optional(), timeout: z.number().int().positive().optional() }),
  z.object({ op: z.literal("scroll"), target: t.optional(), dy: z.number().optional() }),
  z.object({ op: z.literal("resize"), width: z.number().int().positive(), height: z.number().int().positive() }),
]);

export type Command = z.infer<typeof commandSchema>;
