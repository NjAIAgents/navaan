import { ItemList } from "./Songs";

// Blog (NAV-69): a keyword becomes a trending topic, then a dev.to post, a LinkedIn article and a LinkedIn post under the owner's own name.
export default function Blog() { return <ItemList type="blog" title="Blog" blurb="Pick a trending topic; it becomes a dev.to post, a LinkedIn article and a LinkedIn post." noun="post" />; }
