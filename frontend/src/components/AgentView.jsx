import {
  useVoiceAssistant,
  BarVisualizer,
  useLocalParticipant,
  useTrackTranscription,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { useEffect, useRef } from "react";

export default function AgentView() {
  const { state, audioTrack, agentTranscriptions } = useVoiceAssistant();
  const localParticipant = useLocalParticipant();
  const bottomRef = useRef(null);

  const localTrackRef = {
    publication: localParticipant.microphoneTrack,
    source: Track.Source.Microphone,
    participant: localParticipant.localParticipant,
  };
  const { segments: userSegments } = useTrackTranscription(localTrackRef);

  const allSegments = [
    ...(agentTranscriptions || []).map((s) => ({
      ...s,
      speaker: "Lila",
      isAgent: true,
    })),
    ...(userSegments || []).map((s) => ({
      ...s,
      speaker: "You",
      isAgent: false,
    })),
  ].sort((a, b) => (a.firstReceivedTime ?? 0) - (b.firstReceivedTime ?? 0));

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [allSegments.length]);

  const stateLabel = {
    initializing: "Starting up\u2026",
    listening: "Listening",
    thinking: "Thinking\u2026",
    speaking: "Speaking",
  };

  return (
    <div className="agent-view">
      <div className="visualizer-container">
        <BarVisualizer
          state={state}
          trackRef={audioTrack}
          barCount={7}
          style={{ height: "100px" }}
        />
        <p className="agent-state">{stateLabel[state] || state}</p>
      </div>

      <div className="transcript-panel">
        <h3 className="transcript-title">Conversation</h3>
        <div className="transcript-messages">
          {allSegments.map((seg, i) => (
            <div
              key={seg.id || i}
              className={`transcript-line ${seg.isAgent ? "agent" : "user"}`}
            >
              <span className="speaker">{seg.speaker}</span>
              <span className="text">{seg.text}</span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
