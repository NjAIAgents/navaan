import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Lyrics } from "./Lyrics";

afterEach(cleanup);
const lines: [number, string][] = [[2, "line one"], [68, "line two"]];

describe("Lyrics", () => {
  it("makes each timed line a button that says when it starts and sends that second", () => {
    const pick = vi.fn(); render(<Lyrics plain="" timed={lines} position={0} follow={false} onPick={pick} />);
    expect(screen.getByRole("button", { name: "Play from 1:08: line two" })).toHaveTextContent("1:08line two"); fireEvent.click(screen.getByRole("button", { name: "Play from 1:08: line two" })); expect(pick).toHaveBeenCalledWith(68);
  });
  it("shows plain lines with no buttons when picking is not offered", () => {
    render(<Lyrics plain="" timed={lines} position={0} follow={false} />); expect(screen.queryAllByRole("button")).toHaveLength(0); expect(screen.getByText("line one")).toBeInTheDocument();
  });
  it("says a jump may land a little off when the times are estimated", () => {
    render(<Lyrics plain={"line one\nline two"} timed={null} position={0} follow duration={200} onPick={() => undefined} />);
    expect(screen.getByText(/Lines follow the song approximately, so a jump may land a little off/)).toBeInTheDocument(); expect(screen.getAllByRole("button")).toHaveLength(2);
  });
});
