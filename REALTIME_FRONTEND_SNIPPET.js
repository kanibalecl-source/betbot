// Realtime WebSocket client
const ws = new WebSocket("wss://TWOJ-DOMAIN/api/v1/realtime/ws");

ws.onopen = () => {
  console.log("Realtime connected");
  ws.send("ping");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Realtime event:", data);
};

ws.onclose = () => {
  console.log("Realtime disconnected");
};
