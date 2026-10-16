const PATHS: Record<string, string> = {
  home: "M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  studio: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
  library: "M4 4v16M9 4v16M14 6l5 14M14 6l-1-2",
  albums: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.3-4.3",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM19 12l2-1-1-3-2 .5-1.5-1.5L17 5l-3-1-1 2h-2L10 4 7 5l.5 2L6 8.5 4 8l-1 3 2 1v2l-2 1 1 3 2-.5 1.5 1.5L7 21l3 1 1-2h2l1 2 3-1-.5-2 1.5-1.5 2 .5 1-3-2-1z",
  check: "M5 12l5 5L20 7",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4",
  sun: "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  moon: "M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z",
  device: "M4 5h16v11H4zM8 21h8M12 16v5",
  out: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  chevron: "M9 6l6 6-6 6",
  external: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2",
  chart: "M4 20V10M10 20V4M16 20v-8M22 20H2",
  play: "M8 5v14l11-7z",
  pause: "M7 5h4v14H7zM13 5h4v14h-4z",
  plus: "M12 5v14M5 12h14",
  next: "M6 5v14l9-7zM17 5h2v14h-2z",
  prev: "M18 5v14l-9-7zM5 5h2v14H5z",
  download: "M12 3v12M7 11l5 5 5-5M5 20h14",
  expand: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
  close: "M6 6l12 12M18 6L6 18",
  share: "M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v14",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
  quote: "M7 7h4v4H7zM13 7h4v4h-4zM7 11c0 3-1 5-3 6M13 11c0 3-1 5-3 6",
};
export type IconName = keyof typeof PATHS;

export function Icon({ name, filled = false }: { name: IconName; filled?: boolean }) {
  return (
    <svg className={"ic" + (filled ? " f" : "")} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={PATHS[name]} />
    </svg>
  );
}
