import { lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import Home from "./pages/Home";
import { useMe } from "./lib/me";
import Placeholder from "./pages/Placeholder";
import Songs from "./pages/Songs";
import StudioHome from "./pages/StudioHome";

// Each screen is loaded when it is opened, so the first paint carries only the shell, Home and the Songs list.
const Browse = lazy(() => import("./pages/Browse"));
const ListenerSong = lazy(() => import("./pages/ListenerSong"));
const Account = lazy(() => import("./pages/Account"));
const ListenerAlbum = lazy(() => import("./pages/ListenerAlbum"));
const Settings = lazy(() => import("./pages/Settings"));
const Cloud = lazy(() => import("./pages/Cloud"));
const Security = lazy(() => import("./pages/Security"));
const Albums = lazy(() => import("./pages/Albums"));
const Album = lazy(() => import("./pages/Album"));
const Library = lazy(() => import("./pages/Library"));
const Playlist = lazy(() => import("./pages/Playlist"));
const Plans = lazy(() => import("./pages/Plans"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Approvals = lazy(() => import("./pages/Approvals"));
const Inspiration = lazy(() => import("./pages/Inspiration"));
const Schedule = lazy(() => import("./pages/Schedule"));
const Search = lazy(() => import("./pages/Search"));
const Song = lazy(() => import("./pages/Song"));

// Home is the studio dashboard for the studio side and Browse for a listener.
function HomeSwitch() { const me = useMe(); return !me.ready ? <p className="mu" role="status">Loading…</p> : me.studio ? <Home /> : <Browse />; }

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<HomeSwitch />} />
        <Route path="browse" element={<Browse />} />
        <Route path="song/:slug" element={<ListenerSong />} />
        <Route path="album/:slug" element={<ListenerAlbum />} />
        <Route path="account" element={<Account />} />
        <Route path="account/security" element={<Security />} />
        <Route path="studio" element={<StudioHome />} />
        <Route path="studio/songs" element={<Songs />} />
        <Route path="studio/songs/:slug" element={<Song />} />
        <Route path="studio/inspiration" element={<Inspiration />} />
        <Route path="studio/inspiration/:slug" element={<Song />} />
        <Route path="studio/podcasts" element={<Placeholder title="Podcasts" blurb="Spoken episodes will live here, in a later release." />} />
        <Route path="studio/approvals" element={<Approvals />} />
        <Route path="studio/schedule" element={<Schedule />} />
        <Route path="studio/analytics" element={<Analytics />} />
        <Route path="studio/settings" element={<Settings />} />
        <Route path="studio/cloud" element={<Cloud />} />
        <Route path="search" element={<Search />} />
        <Route path="library" element={<Library />} />
        <Route path="library/playlists/:id" element={<Playlist />} />
        <Route path="plans" element={<Plans />} />
        <Route path="albums" element={<Albums />} />
        <Route path="albums/:slug" element={<Album />} />
        <Route path="*" element={<Placeholder title="Not found" blurb="That page does not exist." />} />
      </Route>
    </Routes>
  );
}
