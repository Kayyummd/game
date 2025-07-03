const message = document.getElementById("message");

// 🔐 Login function
function login() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();

  if (!username || !password) {
    showMessage("Please fill in both fields.");
    return;
  }

  fetch("/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ username, password })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      showMessage("Login successful! 🎉", true);
      setTimeout(() => {
        // ✅ Redirect to room with username in query string
        window.location.href = `/room?username=${encodeURIComponent(username)}&host=true`;
      }, 1000);
    } else {
      showMessage(data.message || "Login failed.");
    }
  })
  .catch(() => showMessage("Server error. Please try again."));
}

// 🧾 Register function
function register() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();

  if (!username || !password) {
    showMessage("Please fill in both fields.");
    return;
  }

  fetch("/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ username, password })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      showMessage("Registration successful! ✅", true);
    } else {
      showMessage(data.message || "Registration failed.");
    }
  })
  .catch(() => showMessage("Server error. Please try again."));
}

// 🔔 Display message to user
function showMessage(msg, success = false) {
  message.innerText = msg;
  message.style.color = success ? "#00cc00" : "#cc0000";
}
