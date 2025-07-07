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
  .then(res => {
    if (!res.ok) throw new Error("Invalid credentials");
    return res.json();
  })
  .then(data => {
    if (data.success) {
      showMessage("Login successful! 🎉", true);

      setTimeout(() => {
        // ✅ Route to /admin if admin user
        if (username.toLowerCase() === "admin") {
          window.location.href = "/admin";
        } else {
          window.location.href = "/game";  // regular user route
        }
      }, 1000);
    } else {
      showMessage(data.message || "Login failed.");
    }
  })
  .catch(err => {
    console.error(err);
    showMessage("Login failed: " + (err.message || "Server error."));
  });
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
  .catch(err => {
    console.error(err);
    showMessage("Registration error: " + (err.message || "Server issue"));
  });
}

// 🔔 Show feedback message
function showMessage(msg, success = false) {
  message.innerText = msg;
  message.style.color = success ? "#00cc00" : "#cc0000";
  message.style.opacity = 1;

  // Optional fade out after 4 seconds
  setTimeout(() => {
    message.style.opacity = 0;
  }, 4000);
}

// ⌨️ Allow pressing "Enter" to trigger login
document.addEventListener("keydown", function (e) {
  if (e.key === "Enter") {
    login();
  }
});
