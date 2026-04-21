import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SoundWaveform } from "./SoundWaveform";

describe("SoundWaveform", () => {
  it("renders loading placeholders while waveform data is pending", () => {
    render(<SoundWaveform loading />);

    expect(screen.getByRole("img", { name: "Loading waveform preview" })).toBeInTheDocument();
  });

  it("marks played bars and shows a playhead when progress is available", () => {
    const { container } = render(<SoundWaveform peaks={[0.2, 0.5, 0.9, 0.4]} progress={0.5} isPlaying />);

    expect(container.querySelectorAll(".sound-waveform-bar.played")).toHaveLength(2);
    expect(container.querySelector(".sound-waveform-playhead.active")).toBeInTheDocument();
  });

  it("renders a retry affordance for waveform errors", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();

    render(<SoundWaveform error="Waveform data is not ready yet." onRetry={onRetry} />);

    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
