// Configuración
const socket = new WebSocket('ws://' + window.location.host + '/init');
const lines = document.getElementById("lines");
const linesContainer = document.getElementById("linescontainer");
const chatInput = document.getElementById("chatinput");
const loadingBar = document.getElementById("loadingbar");
const connectionStatus = document.getElementById("connection-status");

let linesData = [];
let currentResponseDiv = null;

//  Manejar teclas
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        submitText();
        return false;
    }
}

//  Auto-resize del textarea
function autoResize(element) {
    element.style.height = 'auto';
    element.style.height = Math.min(element.scrollHeight, 150) + 'px';
}

//  Obtener texto limpio
function getInputText() {
    return chatInput.innerText.trim();
}

//  Limpiar input
function clearInput() {
    chatInput.innerText = "";
    chatInput.style.height = 'auto';
    chatInput.focus();
}

//  Enviar mensaje
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
        console.log(" Historial enviado:", linesData.length, "mensajes");
    } catch (error) {
        console.error(" Error enviando:", error);
        alert("Error de conexión. Recarga la página.");
        return false;
    }

    // 5. Mostrar loading
    loadingBar.style.display = 'flex';
    scrollToBottom();

    // 6. Crear contenedor de respuesta del asistente
    currentResponseDiv = document.createElement("div");
    currentResponseDiv.className = "line server";
    currentResponseDiv.innerHTML = '<span class="typing-indicator">...</span>';
    lines.appendChild(currentResponseDiv);

    // 7. Agregar placeholder al historial
    linesData.push({ role: "assistant", content: "" });

    scrollToBottom();
    return false;
}

//  Actualizar respuesta en tiempo real
function updateLastResponse(content) {
    if (!currentResponseDiv) {
        console.warn(" No hay div de respuesta activo");
        return;
    }

    const lastIndex = linesData.length - 1;
    if (linesData[lastIndex] && linesData[lastIndex].role === "assistant") {
        linesData[lastIndex].content += content;
        currentResponseDiv.innerHTML = marked.parse(linesData[lastIndex].content);
        scrollToBottom();
    } else {
        console.warn(" No hay mensaje assistant en linesData");
    }
}


function finishResponse(data) {
    console.log("✅ Respuesta finalizada");
    loadingBar.style.display = 'none';

    if (currentResponseDiv) {
        currentResponseDiv.removeAttribute("id");

        // ✅ MOSTRAR IMÁGENES SI EXISTEN
        if (data && data.images && data.images.length > 0) {
            console.log(`🖼️ Mostrando ${data.images.length} imágenes`);

            const imagesContainer = document.createElement("div");
            imagesContainer.className = "images-container";

            data.images.forEach((img, index) => {
                const imgWrapper = document.createElement("div");
                imgWrapper.className = "image-wrapper";

                // ✅ Usar la nueva ruta /images/ en lugar de /static/images/
                const imgElement = document.createElement("img");
                imgElement.src = img.url.startsWith('/images/')
                    ? img.url
                    : `/images/${img.filename || img.url.split('/').pop()}`;

                imgElement.alt = `Imagen página ${img.page}`;
                imgElement.loading = "lazy";
                imgElement.onclick = () => openImageModal(imgElement.src);

                // Caption con info
                const caption = document.createElement("p");
                caption.innerHTML = `📄 Página ${img.page}`;

                imgWrapper.appendChild(imgElement);
                imgWrapper.appendChild(caption);
                imagesContainer.appendChild(imgWrapper);

                console.log(`  - Imagen ${index + 1}: ${imgElement.src}`);
            });

            currentResponseDiv.appendChild(imagesContainer);
            scrollToBottom();
        }

        currentResponseDiv = null;
    }
}


function openImageModal(imageUrl) {
    const modal = document.createElement("div");
    modal.className = "image-modal";
    modal.onclick = () => modal.remove();

    const img = document.createElement("img");
    img.src = imageUrl;
    img.onclick = (e) => e.stopPropagation();

    const closeBtn = document.createElement("div");
    closeBtn.className = "image-modal-close";
    closeBtn.innerHTML = "✕ Cerrar";
    closeBtn.onclick = () => modal.remove();

    modal.appendChild(closeBtn);
    modal.appendChild(img);
    document.body.appendChild(modal);
}
//  Scroll al fondo
function scrollToBottom() {
    linesContainer.scrollTop = linesContainer.scrollHeight;
}

//  Manejar mensajes del servidor
socket.onmessage = function(event) {
    try {
        const rdata = JSON.parse(event.data);
        console.log(" [WS] Acción:", rdata.action);

        switch(rdata.action) {
            case "init_system_response":
                console.log(" Iniciando respuesta...");
                break;
                
            case "append_system_response":
                updateLastResponse(rdata.content);
                break;
                
            case "finish_system_response":
                finishResponse(rdata);  //  Pasar datos completos (incluye images)
                break;
                
            case "error":
                loadingBar.style.display = 'none';
                alert(" Error: " + rdata.message);
                break;
                
            default:
                console.warn(" Acción desconocida:", rdata.action);
        }
    } catch (e) {
        console.error(" Error parseando mensaje:", e);
        console.error("Datos raw:", event.data);
    }
};

//  Estado de conexión
socket.onopen = () => {
    console.log(" WebSocket CONNECTED");
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
    console.error(" WebSocket ERROR:", error);
};

//  Focus al cargar
window.onload = () => {
    if (chatInput) chatInput.focus();
};

