import { lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import Home from "./pages/Home";
import { useMe } from "./lib/me";
import Placeholder from "./pages/Placeholder";
import Songs from "./pages/Songs";
import StudioHome from "./pages/StudioHome";
import { MembersOnly } from "./components/GuestPitch";
import { Loading } from "./components/Loading";

// Each screen is loaded when it is opened, so the first paint carries only the shell, Home and the Songs list.
const Browse = lazy(() => import("./pages/Browse"));
const ListenerSong = lazy(() => import("./pages/ListenerSong"));
const Account = lazy(() => import("./pages/Account"));
const ListenerAlbum = lazy(() => import("./pages/ListenerAlbum"));
const Settings = lazy(() => import("./pages/Settings"));
const Cloud = lazy(() => import("./pages/Cloud"));
const Security = lazy(() => import("./pages/Security"));
const Join = lazy(() => import("./pages/Join"));
const Albums = lazy(() => import("./pages/Albums"));
const Album = lazy(() => import("./pages/Album"));
const Library = lazy(() => import("./pages/Library"));
const Playlist = lazy(() => import("./pages/Playlist"));
const Plans = lazy(() => import("./pages/Plans"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Approvals = lazy(() => import("./pages/Approvals"));
const Inspiration = lazy(() => import("./pages/Inspiration"));
const Aha = lazy(() => import("./pages/Aha"));
const Schedule = lazy(() => import("./pages/Schedule"));
const Search = lazy(() => import("./pages/Search"));
const Song = lazy(() => import("./pages/Song"));

// Home is the studio dashboard for the studio side and Browse for a listener.
function HomeSwitch() { const me = useMe(); return !me.ready ? <Loading /> : me.studio ? <Home /> : <Browse />; }

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<HomeSwitch />} />
        <Route path="browse" element={<Browse />} />
        <Route path="song/:slug" element={<ListenerSong />} />
        <Route path="album/:slug" element={<ListenerAlbum />} />
        <Route path="account" element={<MembersOnly><Account /></MembersOnly>} />
        <Route path="account/security" element={<MembersOnly><Security /></MembersOnly>} />
        <Route path="studio" element={<MembersOnly studio><StudioHome /></MembersOnly>} />
        <Route path="studio/songs" element={<MembersOnly studio><Songs /></MembersOnly>} />
        <Route path="studio/songs/:slug" element={<MembersOnly studio><Song /></MembersOnly>} />
        <Route path="studio/inspiration" element={<MembersOnly studio><Inspiration /></MembersOnly>} />
        <Route path="studio/inspiration/:slug" element={<MembersOnly studio><Song /></MembersOnly>} />
        <Route path="studio/aha" element={<MembersOnly studio><Aha /></MembersOnly>} />
        <Route path="studio/aha/:slug" element={<MembersOnly studio><Song /></MembersOnly>} />
        <Route path="studio/podcasts" element={<MembersOnly studio><Placeholder title="Podcasts" blurb="Spoken episodes will live here, in a later release." /></MembersOnly>} />
        <Route path="studio/approvals" element={<MembersOnly studio><Approvals /></MembersOnly>} />
        <Route path="studio/schedule" element={<MembersOnly studio><Schedule /></MembersOnly>} />
        <Route path="studio/analytics" element={<MembersOnly studio><Analytics /></MembersOnly>} />
        <Route path="studio/settings" element={<MembersOnly studio><Settings /></MembersOnly>} />
        <Route path="studio/cloud" element={<MembersOnly studio><Cloud /></MembersOnly>} />
        <Route path="search" element={<Search />} />
        <Route path="library" element={<Library />} />
        <Route path="join" element={<Join />} />
        <Route path="library/playlists/:id" element={<MembersOnly><Playlist /></MembersOnly>} />
        <Route path="plans" element={<MembersOnly><Plans /></MembersOnly>} />
        <Route path="albums" element={<MembersOnly><Albums /></MembersOnly>} />
        <Route path="albums/:slug" element={<MembersOnly><Album /></MembersOnly>} />
        <Route path="*" element={<Placeholder title="Not found" blurb="That page does not exist." />} />
      </Route>
    </Routes>
  );
}
