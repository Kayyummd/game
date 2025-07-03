<script>
  // Extract username and host from URL
  const urlParams = new URLSearchParams(window.location.search);
  const username = urlParams.get("username") || "Player";
  const isHost = urlParams.get("host") === "true";

  // Generate or use existing room code
  function generateRoomCode(length = 6) {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let code = "";
    for (let i = 0; i < length; i++) {
      code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return code;
  }

  // Called when host clicks "Create Room"
  function createRoom() {
    const room = generateRoomCode();
    window.location.href = `multiplayer_game.html?room=${room}&username=${encodeURIComponent(username)}&host=true`;
  }

  // Called when guest clicks "Join Room"
  function joinRoom() {
    const input = document.getElementById("room-code-input");
    const room = input.value.trim().toUpperCase();
    if (!room) {
      alert("Enter a valid room code.");
      return;
    }
    window.location.href = `multiplayer_game.html?room=${room}&username=${encodeURIComponent(username)}&host=false`;
  }
</script>
