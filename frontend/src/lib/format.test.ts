import { formatDuration } from "./format";

describe("formatDuration", () => {
  it("formats seconds to mm:ss", () => {
    expect(formatDuration(95)).toBe("1:35");
  });

  it("handles invalid or missing durations", () => {
    expect(formatDuration(null)).toBe("Unknown");
    expect(formatDuration(Number.NaN)).toBe("Unknown");
  });
});
