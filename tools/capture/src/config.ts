import { z } from "zod";

const configSchema = z.object({
  PROFILE_DIR: z.string().min(1),
  OUTPUT_DIR: z.string().min(1),
  PORT: z.coerce.number().int().min(1024).max(65535).default(9555),
  VIEWPORT_WIDTH: z.coerce.number().int().min(800).default(1600),
  VIEWPORT_HEIGHT: z.coerce.number().int().min(600).default(900),
  RECORD_VIDEO: z.enum(["0", "1"]).default("1"),
  CHANNEL: z.enum(["chromium", "chrome", "msedge"]).default("chromium"),
});

export type DriverConfig = {
  profileDir: string;
  outputDir: string;
  port: number;
  viewport: { width: number; height: number };
  recordVideo: boolean;
  channel: "chromium" | "chrome" | "msedge";
};

export function loadConfig(env: NodeJS.ProcessEnv): DriverConfig {
  const parsed = configSchema.parse({
    PROFILE_DIR: env.CAPTURE_PROFILE_DIR,
    OUTPUT_DIR: env.CAPTURE_OUTPUT_DIR,
    PORT: env.CAPTURE_PORT,
    VIEWPORT_WIDTH: env.CAPTURE_VIEWPORT_WIDTH,
    VIEWPORT_HEIGHT: env.CAPTURE_VIEWPORT_HEIGHT,
    RECORD_VIDEO: env.CAPTURE_RECORD_VIDEO,
    CHANNEL: env.CAPTURE_CHANNEL,
  });
  return {
    profileDir: parsed.PROFILE_DIR,
    outputDir: parsed.OUTPUT_DIR,
    port: parsed.PORT,
    viewport: { width: parsed.VIEWPORT_WIDTH, height: parsed.VIEWPORT_HEIGHT },
    recordVideo: parsed.RECORD_VIDEO === "1",
    channel: parsed.CHANNEL,
  };
}
