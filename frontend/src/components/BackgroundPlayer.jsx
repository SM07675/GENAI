import { useEffect, useRef } from "react";
import { useAppStore } from "../store/appStore";

export default function BackgroundPlayer() {
  const backgroundMedia = useAppStore((state) => state.backgroundMedia);
  const iframeRef = useRef(null);

  if (!backgroundMedia) return null;

  const { video_id, playlist_id } = backgroundMedia;

  let src = "";
  if (video_id) {
    // enablejsapi=1 allows us to control the player programmatically if we wanted to
    src = `https://www.youtube.com/embed/${video_id}?autoplay=1&enablejsapi=1`;
  } else if (playlist_id) {
    src = `https://www.youtube.com/embed/videoseries?list=${playlist_id}&autoplay=1&enablejsapi=1`;
  }

  if (!src) return null;

  return (
    <div style={{ position: "absolute", top: -9999, left: -9999, width: 1, height: 1, opacity: 0.01, pointerEvents: "none" }}>
      <iframe
        ref={iframeRef}
        width="1"
        height="1"
        src={src}
        title="Genie Background Music Player"
        frameBorder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    </div>
  );
}
