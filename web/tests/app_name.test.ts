import { describe, expect, it } from "vitest";

import { APP_NAME } from "../src/app_name";

describe("skeleton", () => {
  it("names the application", () => {
    expect(APP_NAME).toBe("stagecraft-studio");
  });
});
