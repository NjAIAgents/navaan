import { Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import Home from "./pages/Home";
import Placeholder from "./pages/Placeholder";
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
        <Route path="studio/inspiration" element={<Placeholder title="Inspiration" story="NAV-14" blurb="Quotes and short videos." hash="" />} />
        <Route path="studio/podcasts" element={<Placeholder title="Podcasts" story="a later release" blurb="Spoken episodes will live here." />} />
        <Route path="studio/approvals" element={<Placeholder title="Approvals" story="NAV-14" blurb="Everything waiting for your yes, in one list." hash="" />} />
        <Route path="studio/schedule" element={<Placeholder title="Schedule" story="NAV-14" blurb="What publishes when." hash="" />} />
        <Route path="studio/analytics" element={<Placeholder title="Analytics" story="NAV-15" blurb="Numbers, recommendations and interactions." hash="#/analytics" />} />
        <Route path="library" element={<Placeholder title="Library" story="NAV-16" blurb="Everything you have made." hash="" />} />
        <Route path="albums" element={<Placeholder title="Albums" story="NAV-16" blurb="Releases with order, cover and date." hash="" />} />
        <Route path="*" element={<Placeholder title="Not found" story="nothing" blurb="That page does not exist." />} />
      </Route>
    </Routes>
  );
}
