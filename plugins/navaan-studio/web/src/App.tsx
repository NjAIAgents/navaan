import { lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import Home from "./pages/Home";
import Placeholder from "./pages/Placeholder";
import Songs from "./pages/Songs";

// Each screen is loaded when it is opened, so the first paint carries only the shell, Home and the Songs list.
const Library = lazy(() => import("./pages/Library"));
const Playlist = lazy(() => import("./pages/Playlist"));
const Plans = lazy(() => import("./pages/Plans"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Approvals = lazy(() => import("./pages/Approvals"));
const Inspiration = lazy(() => import("./pages/Inspiration"));
const Schedule = lazy(() => import("./pages/Schedule"));
const Search = lazy(() => import("./pages/Search"));
const Song = lazy(() => import("./pages/Song"));

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Home />} />
        <Route path="studio" element={<Placeholder title="Studio" story="the Studio stories (NAV-13, NAV-14, NAV-15)" blurb="Songs, inspiration, approvals, schedule and analytics." hash="" />} />
        <Route path="studio/songs" element={<Songs />} />
        <Route path="studio/songs/:slug" element={<Song />} />
        <Route path="studio/inspiration" element={<Inspiration />} />
        <Route path="studio/inspiration/:slug" element={<Song />} />
        <Route path="studio/podcasts" element={<Placeholder title="Podcasts" story="a later release" blurb="Spoken episodes will live here." />} />
        <Route path="studio/approvals" element={<Approvals />} />
        <Route path="studio/schedule" element={<Schedule />} />
        <Route path="studio/analytics" element={<Analytics />} />
        <Route path="search" element={<Search />} />
        <Route path="library" element={<Library />} />
        <Route path="library/playlists/:id" element={<Playlist />} />
        <Route path="plans" element={<Plans />} />
        <Route path="albums" element={<Placeholder title="Albums" story="NAV-16" blurb="Releases with order, cover and date." hash="" />} />
        <Route path="*" element={<Placeholder title="Not found" story="nothing" blurb="That page does not exist." />} />
      </Route>
    </Routes>
  );
}
