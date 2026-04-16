import { useRoomContext } from "@livekit/components-react";
import { RoomEvent } from "livekit-client";
import { useEffect } from "react";

export default function ShelfSync({ onShelfUpdated }) {
  const room = useRoomContext();

  useEffect(() => {
    const handler = (_payload, _participant, _kind, topic) => {
      if (topic === "shelf_updated") {
        onShelfUpdated();
      }
    };
    room.on(RoomEvent.DataReceived, handler);
    return () => room.off(RoomEvent.DataReceived, handler);
  }, [room, onShelfUpdated]);

  return null;
}
