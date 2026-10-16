import { Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import Home from "./pages/Home";
import Placeholder from "./pages/Placeholder";
import Approvals from "./pages/Approvals";
import Inspiration from "./pages/Inspiration";
import Schedule from "./pages/Schedule";
import Song from "./pages/Song";
import Songs from "./pages/Songs";

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
        <Route path="studio/analytics" element={<Placeholder title="Analytics" story="NAV-15" blurb="Numbers, recommendations and interactions." hash="#/analytics" />} />
        <Route path="library" element={<Placeholder title="Library" story="NAV-16" blurb="Everything you have made." hash="" />} />
        <Route path="albums" element={<Placeholder title="Albums" story="NAV-16" blurb="Releases with order, cover and date." hash="" />} />
        <Route path="*" element={<Placeholder title="Not found" story="nothing" blurb="That page does not exist." />} />
      </Route>
    </Routes>
  );
}
