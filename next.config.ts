import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Next 16 blocks cross-origin requests to dev-only assets, and it treats
  // 127.0.0.1 as a different origin from the localhost it boots on. Opening the
  // app at 127.0.0.1 therefore blocked /_next/hmr, the client bundle never
  // bootstrapped, and every interactive element was dead: the theme toggle, the
  // sidebar collapsibles, the approve buttons, all of it. The page still looked
  // fine because the server render is complete, which is what made it confusing.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
