import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    ignores: ["dist/**", "src/api/schema.ts"],
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
);
