import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { SongDetail } from "../lib/api";
import { ShotsPreview } from "./ShotsPreview";

const shots = { duration: 274.39, shots: [
  { id: 1, label: "Instrumental 1", start: 0, end: 17.15, image: "images/pic_01.png", camera: "push_in", focus: [0.48, 0.7], scene: "At a small window table in a late-night cafe, the woman with the thin silver ring" },
  { id: 2, label: "Verse 1", start: 17.15, end: 40, image: "images/pic_02.png", camera: "pan_left", scene: "Rain on the glass." },
] };
const d = (text: string) => ({ slug: "song-007", text: { "shots.json": text } }) as unknown as SongDetail;
afterEach(cleanup);

describe("ShotsPreview", () => {
  it("shows each shot as its picture with the time it is on screen, the camera move and the scene, in order", () => {
    render(<ShotsPreview d={d(JSON.stringify(shots))} />);
    const items = screen.getAllByRole("listitem"); expect(items).toHaveLength(2);
    expect(screen.getByAltText("Picture for Instrumental 1")).toHaveAttribute("src", "/media/song-007/images~pic_01.png");   // the picture, served by its name
    expect(items[0]).toHaveTextContent("1. Instrumental 1"); expect(items[0]).toHaveTextContent("0:00 to 0:17"); expect(items[0]).toHaveTextContent("camera: push in"); expect(items[0]).toHaveTextContent("late-night cafe");
    expect(items[1]).toHaveTextContent("2. Verse 1"); expect(items[1]).toHaveTextContent("camera: pan left");
  });
  it("shows nothing when the shot list is missing or is not JSON, so the raw text below it is what is shown", () => {
    const { container, rerender } = render(<ShotsPreview d={d("not json {")} />); expect(container).toBeEmptyDOMElement();
    rerender(<ShotsPreview d={d("{}")} />); expect(container).toBeEmptyDOMElement();
  });
});
