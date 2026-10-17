// What each approval gate asks, in words, and which file shows what is being approved. Same wording as the classic page so both read the same.
export const GATE_TITLE: Record<string, string> = {
  lyrics: "Lyrics", quote: "Quote", originality: "Originality and attribution check", suno_download: "Suno download", listen: "Listen to the song",
  visuals_mode: "Choose the visuals", shots: "Shot list", credits: "Spending credits on pictures and clips", captions_setup: "Caption tools download (about 700 MB)",
  media: "Review the videos", publish_youtube: "Upload the video to YouTube (private)", publish_short: "Upload the Short to YouTube (private)",
  instagram_caption: "Instagram caption", publish_instagram: "Publish to Instagram", cloud_upload: "Upload to the cloud bucket", local_cleanup: "Delete the local media", go_public: "Make the YouTube video public",
};
export const GATE_ASK: Record<string, string> = {
  lyrics: "I approve these lyrics.", quote: "I approve this quote and its wording.", originality: "I reviewed the originality and attribution check.",
  suno_download: "I allow one Suno download from my plan allowance (needed to import this song).", listen: "I listened and accept this song.",
  shots: "I approve this shot list; render the video from it.", credits: "I approve spending Suno, Flow and OpenAI credits.",
  captions_setup: "I approve a one-time download of the caption tools (about 700 MB from GitHub and PyPI, saved outside the repo).", media: "I reviewed the videos and approve them.",
  publish_youtube: "Upload the full video to YouTube. It stays private; nobody can see it yet.", publish_short: "Upload the Short to YouTube. It stays private; nobody can see it yet.",
  go_public: "Make the YouTube video and Short public now. Then the Instagram Reel can go out.", instagram_caption: "I approve this Instagram caption.",
  publish_instagram: "Publish to Instagram now.", cloud_upload: "Upload this finished song to my cloud bucket.",
  local_cleanup: "Delete the local media of this song now. The bucket copy is checked file by file first; text and meta stay.",
};
// The file that holds what is being approved.
export const GATE_FILE: Record<string, string> = { lyrics: "lyrics.txt", quote: "quote.json", originality: "originality.json", shots: "shots.json", instagram_caption: "instagram.txt" };
// Approving these spends credits or reaches the outside world, or cannot be undone: ask twice.
export const RISKY = new Set(["credits", "captions_setup", "suno_download", "publish_youtube", "publish_short", "publish_instagram", "go_public", "local_cleanup"]);
const STEP: Record<string, string> = {
  lyrics: "Write lyrics and style", suno: "Generate the song on Suno", suno_import: "Import the song from Suno", visuals_mode: "Choose the visuals", visuals: "Make the visuals", captions: "Sync the captions",
  video: "Build the video", youtube_meta: "Write the YouTube text", publish_youtube: "Upload to YouTube", youtube_short: "Make the Short", instagram_caption: "Write the Instagram caption",
  go_public: "Make it public", publish_instagram: "Post the Reel", archive: "Archive to the cloud", cleanup: "Clean up local files", quote: "Write the quote", originality: "Check originality",
  narrate: "Narrate the quote (ElevenLabs)", narration: "Time the narration to the voice", background_prompt: "Write the background prompt",
  background: "Make the background", typeset: "Plan the typography", render: "Render the video",
  prompts: "Write the picture plan", pictures: "Create the pictures", poster: "Make the poster", shots: "Plan the shots", motion_plan: "Plan what moves", motion_clips: "Make the moving pictures", reel: "Build the vertical reel",
};
export const stepLabel = (id: string) => STEP[id] ?? id.replace(/_/g, " ");
export const gateTitle = (g: string) => GATE_TITLE[g] ?? g.replace(/_/g, " ");
