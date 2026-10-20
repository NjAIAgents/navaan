// What each approval gate asks, in words, and which file shows what is being approved. Same wording as the classic page so both read the same.
export const GATE_TITLE: Record<string, string> = {
  lyrics: "Lyrics", quote: "Quote", originality: "Originality and attribution check", suno_download: "Suno download", listen: "Listen to the song",
  visuals_mode: "Choose the visuals", shots: "Shot list", edit_plan: "Edit plan", credits: "Approve the spend", captions_setup: "Caption tools download (about 700 MB)",
  media: "Review the videos", publish_youtube: "Upload the video to YouTube (private)", publish_short: "Upload the Short to YouTube (private)",
  instagram_caption: "Instagram caption", publish_instagram: "Publish to Instagram", cloud_upload: "Upload to the cloud bucket", local_cleanup: "Delete the local media", go_public: "Make the YouTube video public",
  topic: "Pick the topic",
};
export const GATE_ASK: Record<string, string> = {
  lyrics: "I approve these lyrics.", quote: "I approve this quote and its wording.", originality: "I reviewed the originality and attribution check.",
  suno_download: "I allow one Suno download from my plan allowance (needed to import this song).", listen: "I listened and accept this song.",
  shots: "I approve this shot list; render the video from it.", edit_plan: "I approve this edit plan: the cuts, the framing, the sound and the text. Render the reel from it.", credits: "I approve spending Suno, Flow and OpenAI credits.",
  captions_setup: "I approve a one-time download of the caption tools (about 700 MB from GitHub and PyPI, saved outside the repo).", media: "I reviewed the videos and approve them.",
  publish_youtube: "Upload the video to YouTube, and the Short when there is one. Both stay private; nobody can see them yet.", publish_short: "Upload the Short to YouTube. It stays private; nobody can see it yet.",
  go_public: "Make the YouTube video and Short public now.", instagram_caption: "I approve this Instagram caption.",
  publish_instagram: "Publish to Instagram now.", cloud_upload: "Archive this finished song to my cloud bucket, then delete the local copy. Nothing is deleted unless every file is checked in the bucket first.",
  local_cleanup: "Delete the local media of this song now. The bucket copy is checked file by file first; text and meta stay.",
  topic: "Pick one of the suggested topics. You can reword its title and angle first.",
};
// The file that holds what is being approved.
export const GATE_FILE: Record<string, string> = { lyrics: "lyrics.txt", quote: "quote.json", originality: "originality.json", edit_plan: "edl.json", shots: "shots.json", instagram_caption: "instagram.txt" };
// Approving these spends credits or reaches the outside world, or cannot be undone: ask twice.
export const RISKY = new Set(["credits", "captions_setup", "suno_download", "publish_youtube", "publish_short", "publish_instagram", "go_public", "local_cleanup"]);
const STEP: Record<string, string> = {
  lyrics: "Write lyrics and style", suno: "Generate the song on Suno", suno_import: "Import the song from Suno", visuals_mode: "Choose the visuals", visuals: "Make the visuals", captions: "Sync the captions",
  video: "Build the video", youtube_meta: "Write the YouTube text", publish_youtube: "Upload to YouTube", youtube_short: "Make the Short", instagram_caption: "Write the Instagram caption",
  go_public: "Make it public", publish_instagram: "Post the Reel", archive: "Archive to the cloud", cleanup: "Clean up local files", quote: "Write the quote", originality: "Check originality",
  ingest: "Shrink the footage", direct: "Plan the reel with Claude", edit_check: "Check the edit plan", critique: "Review the render",
  narrate: "Narrate the quote (ElevenLabs)", narration: "Time the narration to the voice", background_prompt: "Write the background prompt", trends: "Look up what is trending", topics: "Suggest 5 topics", research: "Research the topic", outline: "Outline the post", write: "Write the drafts", factcheck: "Fact-check the drafts", factcheck_loop: "Send failing claims back", review: "Review the drafts", edit: "Edit the drafts",
  background: "Make the background", typeset: "Plan the typography", render: "Render the video",
  prompts: "Write the picture plan", pictures: "Create the pictures", shots: "Plan the shots", motion_plan: "Plan what moves", motion_clips: "Make the moving pictures", reel: "Build the vertical reel",
};
export const stepLabel = (id: string) => STEP[id] ?? id.replace(/_/g, " ");
export const gateTitle = (g: string) => GATE_TITLE[g] ?? g.replace(/_/g, " ");

// What a step does, in one plain sentence, shown on a step that has not run yet.
const WHAT: Record<string, string> = {
  suno_import: "Brings the song's words and sound in from Suno.", visuals_mode: "You choose how the video gets its pictures.", prompts: "The director writes the story, the character and one picture prompt for each shot.",
  pictures: "Paints the pictures from the plan with OpenAI.", shots: "Lays the pictures along the song: when each appears and how the camera moves.", motion_plan: "Marks what moves in each picture (steam, cloth, flames); the rest stays still.",
  motion_clips: "Makes a short moving loop for each picture that has something marked to move.", captions: "Times every lyric line to the singing.", reel: "Builds the vertical reel from the best part of the song.",
  video: "Builds the full video from the pictures, their moves and the captions.", youtube_meta: "Writes the YouTube title, description and tags. Nothing is sent.", publish_youtube: "Uploads the video to YouTube as private.",
  youtube_short: "Uploads the reel to YouTube as a private Short.", go_public: "Makes the YouTube video and Short public.", instagram_caption: "Writes the Instagram caption for you to review.",
  publish_instagram: "Posts the reel to Instagram.", archive: "Copies the finished song to the cloud bucket.", cleanup: "Deletes the local copies, only after the bucket has been checked file by file.",
  quote: "Writes or picks the quote.", originality: "Checks the quote's originality and attribution on the web.", background_prompt: "Writes the prompt for the background picture.", background: "Makes the background picture.",
  ingest: "Makes a small working copy of your video, deletes the big original once the copy is checked, and takes still frames and sound facts for Claude.", direct: "Claude looks at the scenes, suggests a quote that fits them, and plans the cuts, framing, look, sound and music. Nothing is made yet.",
  edit_check: "Checks the edit plan against the footage, so a bad plan fails before anything is rendered.", critique: "Claude looks at the rendered reel and tells you what, if anything, to change. It advises; you decide.",
  narrate: "Speaks the quote with ElevenLabs.", narration: "Times each line of the quote to the voice.", typeset: "Plans the typography, the timing and the music under the voice.", render: "Renders the vertical video.",
  trends: "Reads what Hacker News, dev.to and Google Trends show for your keyword. Free, no keys.", topics: "Claude searches the web and suggests 5 timely topics, each with why now, the angle and its sources.",
  research: "Reads primary sources for the topic you picked and lists every claim the post may make, each with its source.", outline: "Plans the sections and which claims each one uses.",
  write: "Writes the dev.to post and adapts it into the LinkedIn article, stating only the listed claims.", factcheck: "Checks every statement in both drafts against its source.",
  factcheck_loop: "Sends failing claims back to the writer, twice at most; after that it stops and asks you.", review: "Notes what to fix in structure, clarity and depth. It changes nothing.", edit: "Applies the review notes to both drafts without changing any fact.",
};
export const stepWhat = (id: string) => WHAT[id] ?? "";
// What an approval does once it stops asking, for the confirmation before it is switched off.
export const riskText = (g: string) => (g === "local_cleanup" ? "deletes local media" : g === "credits" || g === "captions_setup" || g === "suno_download" ? "spends credits or downloads tools" : "reaches the outside world, such as uploading or posting");
