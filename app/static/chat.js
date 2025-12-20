let token = null;

async function login() {
    const res = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: "admin", password: "1234" })
    });
    const data = await res.json();
    token = data.access_token;
}

const chatDiv = document.getElementById("chat");

function addMessage(text, cls) {
    const div = document.createElement("div");
    div.className = `message ${cls}`;
    div.textContent = text;
    chatDiv.appendChild(div);
    chatDiv.scrollTop = chatDiv.scrollHeight;
}

async function send() {
    if (!token) await login();
    const q = document.getElementById("question");
    const question = q.value.trim(); if (!question) return; q.value = "";
    addMessage("👤 " + question, "user");

    const response = await fetch("/rag", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
        body: JSON.stringify({ question: question, model: "llama2" })
    });
    const data = await response.json();
    addMessage("🤖 " + data.answer, "ai");
    addMessage("📄 Fuentes: " + data.sources.join(", "), "ai");
}
