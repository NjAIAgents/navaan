import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Cover, albumFace } from "./Cover";
import type { AlbumRow } from "../lib/api";

afterEach(cleanup);
const album = (o: Partial<AlbumRow>): AlbumRow => ({ id: "1", slug: "raat-ke-baad", title: "Raat Ke Baad", kind: "album", status: "published", release_date: null, description: "", tracks: [
  { slug: "song-001", title: "A", position: 1, status: "published", licence: "confirmed", art: null }, { slug: "song-002", title: "B", position: 2, status: "published", licence: "confirmed", art: { colour: "#112233" } }], ...o });

describe("albumFace: what an album shows", () => {
  it("is its own cover when it has one: a published album from the sized public pictures, a draft from the owner's file", () => {
    expect(albumFace(album({ art: { colour: "#445566", v: 7 } }))).toEqual({ slug: "raat-ke-baad", art: { colour: "#445566", v: 7, album: true } });
    expect(albumFace(album({ status: "draft", art: { colour: null, v: 7 } }))).toEqual({ slug: "raat-ke-baad", art: { colour: null, v: 7, album: true, src: "/api/albums/cover/raat-ke-baad.png?v=7" } });
  });
  it("is the first song's picture without one, and the first song's slug even when no song has a picture", () => {
    expect(albumFace(album({}))).toEqual({ slug: "song-002", art: { colour: "#112233" } });
    expect(albumFace(album({ tracks: album({}).tracks.slice(0, 1) }))).toEqual({ slug: "song-001", art: undefined });
    expect(albumFace(album({ tracks: [] }))).toEqual({ slug: "raat-ke-baad", art: undefined });
  });
});

describe("Cover with an album's art", () => {
  it("asks for /img/album/<slug> sizes, or shows the one file when given a src", () => {
    const { container, rerender } = render(<Cover slug="raat-ke-baad" title="Raat Ke Baad" art={{ colour: null, album: true }} />);
    expect(container.querySelector("img")!.getAttribute("src")).toBe("/img/album/raat-ke-baad/640.jpg");
    expect(container.querySelector("source")!.getAttribute("srcset")).toContain("/img/album/raat-ke-baad/320.avif 320w");
    rerender(<Cover slug="raat-ke-baad" title="Raat Ke Baad" art={{ colour: null, album: true, src: "/api/albums/cover/raat-ke-baad.png?v=7" }} />);
    expect(container.querySelector("img")!.getAttribute("src")).toBe("/api/albums/cover/raat-ke-baad.png?v=7"); expect(container.querySelector("source")).toBeNull();
  });
});

describe("Cover with a song's art: a replaced cover is fetched again", () => {
  it("puts the picture's version in every address, so an old picture kept for a year is not shown", () => {
    const { container, rerender } = render(<Cover slug="song-009" title="Nine" art={{ colour: "#112233", v: 1731824 }} />);
    expect(container.querySelector("img")!.getAttribute("src")).toBe("/img/song-009/640.jpg?v=1731824");
    expect(container.querySelector("source[type='image/avif']")!.getAttribute("srcset")).toBe("/img/song-009/320.avif?v=1731824 320w, /img/song-009/640.avif?v=1731824 640w, /img/song-009/1280.avif?v=1731824 1280w");
    rerender(<Cover slug="song-009" title="Nine" art={{ colour: "#112233", v: 2000001 }} />);
    expect(container.querySelector("img")!.getAttribute("src")).toBe("/img/song-009/640.jpg?v=2000001");   // a new cover, a new address
    rerender(<Cover slug="song-009" title="Nine" art={{ colour: "#112233" }} />);
    expect(container.querySelector("img")!.getAttribute("src")).toBe("/img/song-009/640.jpg");   // no version known: as before
  });
});
