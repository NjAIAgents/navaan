import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ZoomImage } from "./ZoomImage";

afterEach(cleanup);

describe("ZoomImage", () => {
  it("opens the large picture on a click, and closes with Close, Escape or a click outside, giving the focus back", () => {
    render(<ZoomImage src="/media/s/poster_2x3.png?w=360" full="/media/s/poster_2x3.png" alt="Poster" />);
    expect(screen.queryByRole("dialog")).toBeNull(); expect(screen.getByAltText("Poster")).toHaveAttribute("src", "/media/s/poster_2x3.png?w=360");   // the small copy in the page
    const opener = screen.getByRole("button", { name: "Enlarge: Poster" }); fireEvent.click(opener);
    const dlg = screen.getByRole("dialog", { name: "Poster" }); expect(dlg.querySelector("img")).toHaveAttribute("src", "/media/s/poster_2x3.png");   // the large one, not the small copy
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Close" })); expect(screen.queryByRole("dialog")).toBeNull(); expect(opener).toHaveFocus();
    fireEvent.click(opener); fireEvent.keyDown(window, { key: "Escape" }); expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(opener); fireEvent.click(screen.getByRole("dialog")); expect(screen.queryByRole("dialog")).toBeNull();   // outside the picture
    fireEvent.click(opener); fireEvent.click(screen.getByRole("dialog").querySelector("img")!); expect(screen.getByRole("dialog")).toBeInTheDocument();   // a click on the picture itself does not close it
  });
  it("shows the same picture large when there is no separate large version", () => {
    render(<ZoomImage src="/a.png" alt="A" />); fireEvent.click(screen.getByRole("button", { name: "Enlarge: A" }));
    expect(screen.getByRole("dialog").querySelector("img")).toHaveAttribute("src", "/a.png");
  });
});
