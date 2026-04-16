import { useState, useEffect, useCallback } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
} from "@livekit/components-react";
import "@livekit/components-styles";
import useAgentView from "./components/AgentView";
import BookshelfPanel from "./components/BookshelfPanel";
import ShelfSync from "./components/ShelfSync";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function CallView({ shelves, pollShelves, onEndCall }) {
  const { visualizer, transcript } = useAgentView();
  const hasShelves = Object.keys(shelves).length > 0;

  return (
    <>
      <RoomAudioRenderer />
      <ShelfSync onShelfUpdated={pollShelves} />
      <div className="call-layout">
        {visualizer}
        <div className={`call-content ${hasShelves ? "with-shelves" : ""}`}>
          <div className="conversation-panel">
            {transcript && <h2 className="panel-title">Conversation</h2>}
            {transcript}
          </div>
          {hasShelves && <BookshelfPanel shelves={shelves} />}
        </div>
        <button onClick={onEndCall} className="end-btn">
          End Call
        </button>
      </div>
    </>
  );
}

export default function App() {
  const [token, setToken] = useState(null);
  const [lkUrl, setLkUrl] = useState(null);
  const [roomName, setRoomName] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [shelves, setShelves] = useState({});

  const pollShelves = useCallback(async () => {
    if (!roomName) return;
    try {
      const res = await fetch(`${API_BASE}/shelves?room=${roomName}`);
      const data = await res.json();
      setShelves(data);
    } catch (err) {
      console.error("Failed to fetch shelves:", err);
    }
  }, [roomName]);

  useEffect(() => {
    if (!isConnected || !roomName) return;

    pollShelves();
    const interval = setInterval(pollShelves, 3000);
    return () => clearInterval(interval);
  }, [isConnected, roomName, pollShelves]);

  const startCall = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/token`);
      const data = await res.json();
      setToken(data.token);
      setLkUrl(data.url);
      setRoomName(data.room);
      setIsConnected(true);
    } catch (err) {
      console.error("Failed to get token:", err);
    }
  }, []);

  const endCall = useCallback(() => {
    setToken(null);
    setLkUrl(null);
    setRoomName(null);
    setIsConnected(false);
    setShelves({});
  }, []);

  return (
    <div className="app">
      <main className="app-main">
        {!isConnected ? (
          <div className="start-screen">
            <h1 className="app-title">Lila</h1>
            <p className="start-tagline">
              she's read everything.
            </p>
            <button onClick={startCall} className="start-btn">
              Call Lila
            </button>
          </div>
        ) : (
          <LiveKitRoom
            token={token}
            serverUrl={lkUrl}
            connect={true}
            audio={true}
            video={false}
            onDisconnected={endCall}
          >
            <CallView
              shelves={shelves}
              pollShelves={pollShelves}
              onEndCall={endCall}
            />
          </LiveKitRoom>
        )}
      </main>
    </div>
  );
}
