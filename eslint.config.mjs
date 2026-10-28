import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // sigap/deck is its own workspace with its own toolchain, and `dist/` is its
    // build output. Linting a bundle produces errors about minified code that
    // nobody can act on - 16 of them, all from deck/dist - and the deck's own
    // source answers to the open-slide rules, not Next's.
    "sigap/deck/**",
  ]),
]);

export default eslintConfig;
