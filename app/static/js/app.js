// Configuración
const socket = new WebSocket('ws://' + window.location.host + '/init');
const lines = document.getElementById("lines");
const linesContainer = document.getElementById("linescontainer");
const chatInput = document.getElementById("chatinput");
const loadingBar = document.getElementById("loadingbar");
const connectionStatus = document.getElementById("connection-status");

let linesData = [];
let currentResponseDiv = null;  // ✅ Referencia directa al div de respuesta

// ✅ Manejar teclas
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        submitText();
        return false;
    }
}

// ✅ Auto-resize del textarea
function autoResize(element) {
    element.style.height = 'auto';
    element.style.height = Math.min(element.scrollHeight, 150) + 'px';
}

// ✅ Obtener texto limpio
function getInputText() {
    return chatInput.innerText.trim();
}

// ✅ Limpiar input
function clearInput() {
    chatInput.innerText = "";
    chatInput.style.height = 'auto';
    chatInput.focus();
}

// ✅ Enviar mensaje
function submitText() {
    const message = getInputText();
    if (message === "") return false;

    console.log("📤 Enviando mensaje:", message);

    // 1. Mostrar mensaje del usuario
    const userDiv = document.createElement("div");
    userDiv.className = "line user";
    userDiv.innerHTML = marked.parse(message);
    lines.appendChild(userDiv);

    // 2. Limpiar input
    clearInput();

    // 3. Guardar en historial
    linesData.push({ role: "user", content: message });

    // 4. Enviar al servidor
    try {
        socket.send(JSON.stringify(linesData));
        console.log("✅ Historial enviado:", linesData.length, "mensajes");
    } catch (error) {
        console.error("❌ Error enviando:", error);
        alert("Error de conexión. Recarga la página.");
        return false;
    }

    // 5. Mostrar loading
    loadingBar.style.display = 'flex';
    scrollToBottom();

    // 6. ✅ Crear contenedor de respuesta del asistente
    currentResponseDiv = document.createElement("div");
    currentResponseDiv.className = "line server";
    currentResponseDiv.innerHTML = '<span class="typing-indicator">...</span>';
    lines.appendChild(currentResponseDiv);

    // 7. ✅ Agregar placeholder al historial
    linesData.push({ role: "assistant", content: "" });

    scrollToBottom();
    return false;
}

// ✅ Actualizar respuesta en tiempo real
function updateLastResponse(content) {
    // ✅ Usar referencia directa al div
    if (!currentResponseDiv) {
        console.warn("⚠️ No hay div de respuesta activo");
        return;
    }

    // ✅ Buscar el último assistant en linesData
    const lastIndex = linesData.length - 1;
    if (linesData[lastIndex] && linesData[lastIndex].role === "assistant") {
        linesData[lastIndex].content += content;
        currentResponseDiv.innerHTML = marked.parse(linesData[lastIndex].content);
        scrollToBottom();
    } else {
        console.warn("⚠️ No hay mensaje assistant en linesData");
        console.log("linesData:", linesData);
    }
}

// ✅ Finalizar respuesta
function finishResponse() {
    console.log("✅ Respuesta finalizada");
    loadingBar.style.display = 'none';
    currentResponseDiv = null;  // ✅ Limpiar referencia
}

// ✅ Scroll al fondo
function scrollToBottom() {
    linesContainer.scrollTop = linesContainer.scrollHeight;
}

// ✅ Manejar mensajes del servidor
socket.onmessage = function(event) {
    try {
        const rdata = JSON.parse(event.data);
        console.log("📩 [WS] Acción:", rdata.action);
        if (rdata.content) {
            console.log("📩 [WS] Contenido:", rdata.content.substring(0, 50));
        }

        switch(rdata.action) {
            case "init_system_response":
                // ✅ Solo para saludo inicial o nueva respuesta
                if (!currentResponseDiv && linesData.length > 0) {
                    // Si no hay respuesta activa pero hay historial, crear una
                    currentResponseDiv = document.createElement("div");
                    currentResponseDiv.className = "line server";
                    currentResponseDiv.innerHTML = '';
                    lines.appendChild(currentResponseDiv);
                    linesData.push({ role: "assistant", content: "" });
                }
                break;

            case "append_system_response":
                updateLastResponse(rdata.content);
                break;

            case "finish_system_response":
                finishResponse();
                break;

            case "error":
                loadingBar.style.display = 'none';
                alert("⚠️ Error: " + rdata.message);
                break;
        }
    } catch (e) {
        console.error("💥 Error parseando mensaje:", e);
        console.error("Datos raw:", event.data);
    }
};

// ✅ Estado de conexión
socket.onopen = () => {
    console.log("✅ WebSocket CONNECTED");
    if (connectionStatus) {
        connectionStatus.textContent = "● Conectado";
        connectionStatus.className = "status-connected";
    }
};

socket.onclose = () => {
    console.log("🔌 WebSocket CLOSED");
    if (connectionStatus) {
        connectionStatus.textContent = "● Desconectado";
        connectionStatus.className = "status-disconnected";
    }
    loadingBar.style.display = 'none';
    setTimeout(() => location.reload(), 5000);
};

socket.onerror = (error) => {
    console.error("❌ WebSocket ERROR:", error);
};

// ✅ Focus al cargar
window.onload = () => {
    if (chatInput) chatInput.focus();
};