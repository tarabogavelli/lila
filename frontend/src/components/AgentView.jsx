import {
  useVoiceAssistant,
  BarVisualizer,
  useLocalParticipant,
  useTrackTranscription,
  useRoomContext,
} from "@livekit/components-react";
import { Track, RoomEvent } from "livekit-client";
import { useEffect, useRef, useState, useCallback } from "react";
import ToolCallChip from "./ToolCallChip";

export default function useAgentView() {
  const { state, audioTrack, agentTranscriptions } = useVoiceAssistant();
  const localParticipant = useLocalParticipant();
  const bottomRef = useRef(null);
  const room = useRoomContext();
  const [toolEvents, setToolEvents] = useState([]);
  const segmentsRef = useRef([]);

  const onDataReceived = useCallback(
    (payload, _participant, _kind, topic) => {
      if (topic !== "tool_status") return;
      try {
        const data = JSON.parse(new TextDecoder().decode(payload));
        if (data.type === "tool_start") {
          const latest = segmentsRef.current;
          const lastTime = latest.length > 0
            ? Math.max(...latest.map((s) => s.firstReceivedTime ?? 0))
            : 0;
          const toolTime = Math.max(Date.now() / 1000, lastTime + 0.001);
          setToolEvents((prev) => [
            ...prev,
            {
              type: "tool",
              name: data.name,
              id: `tool-${Date.now()}-${Math.random()}`,
              firstReceivedTime: toolTime,
            },
          ]);
        }
      } catch {
        /* ignore parse errors */
      }
    },
    [],
  );

  useEffect(() => {
    room.on(RoomEvent.DataReceived, onDataReceived);
    return () => room.off(RoomEvent.DataReceived, onDataReceived);
  }, [room, onDataReceived]);

  const localTrackRef = {
    publication: localParticipant.microphoneTrack,
    source: Track.Source.Microphone,
    participant: localParticipant.localParticipant,
  };
  const { segments: userSegments } = useTrackTranscription(localTrackRef);

  const speechSegments = [
    ...(agentTranscriptions || []).map((s) => ({
      ...s,
      speaker: "Lila",
      type: "agent",
    })),
    ...(userSegments || []).map((s) => ({
      ...s,
      speaker: "You",
      type: "user",
    })),
  ];
  segmentsRef.current = speechSegments;

  const allSegments = [...speechSegments, ...toolEvents].sort(
    (a, b) => (a.firstReceivedTime ?? 0) - (b.firstReceivedTime ?? 0),
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [allSegments.length]);

  const stateLabel = {
    initializing: "Starting up\u2026",
    listening: "Listening",
    thinking: "Thinking\u2026",
    speaking: "Speaking",
  };

  return {
    visualizer: (
      <div className="visualizer-container">
        <BarVisualizer
          state={state}
          trackRef={audioTrack}
          barCount={5}
          style={{ height: "60px" }}
        />
        <p className="agent-state">{stateLabel[state] || state}</p>
      </div>
    ),
    transcript: allSegments.length > 0 ? (
      <div className="transcript-panel">
        <div className="transcript-messages">
          {allSegments.map((seg, i) =>
            seg.type === "tool" ? (
              <div key={seg.id || i} className="transcript-line tool">
                <ToolCallChip name={seg.name} />
              </div>
            ) : (
              <div
                key={seg.id || i}
                className={`transcript-line ${seg.type}`}
              >
                <span className="speaker">{seg.speaker}</span>
                <span className="text">{seg.text}</span>
              </div>
            ),
          )}
          <div ref={bottomRef} />
        </div>
      </div>
    ) : null,
  };
}
