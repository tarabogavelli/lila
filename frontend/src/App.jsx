import { useState, useEffect, useCallback } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
} from "@livekit/components-react";
import "@livekit/components-styles";
import AgentView from "./components/AgentView";
import BookshelfPanel from "./components/BookshelfPanel";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function App() {
  const [token, setToken] = useState(null);
  const [lkUrl, setLkUrl] = useState(null);
  const [roomName, setRoomName] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [shelves, setShelves] = useState({});

  useEffect(() => {
    if (!isConnected || !roomName) return;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/shelves?room=${roomName}`);
        const data = await res.json();
        setShelves(data);
      } catch (err) {
        console.error("Failed to fetch shelves:", err);
      }
    };

    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, [isConnected, roomName]);

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
      <header className="app-header">
        <h1 className="app-title">Lila</h1>
        <p className="app-subtitle">your personal librarian</p>
      </header>

      <main className="app-main">
        {!isConnected ? (
          <div className="start-screen">
            <p className="start-tagline">
              She's read everything. She has opinions.
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
            <RoomAudioRenderer />
            <div className="call-layout">
              <div className="left-panel">
                <AgentView />
                <button onClick={endCall} className="end-btn">
                  End Call
                </button>
              </div>
              <div className="right-panel">
                <BookshelfPanel shelves={shelves} />
              </div>
            </div>
          </LiveKitRoom>
        )}
      </main>
    </div>
  );
}
