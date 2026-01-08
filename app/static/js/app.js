var chatinput = document.getElementById("chatinput");
var lines = document.getElementById("lines");
var loadingbar = document.getElementById("loadingbar");
var linesData = [];

socket = opensocket("/init");

function submitText() {
    var txt = chatinput.innerText;
    chatinput.innerText = "";

    lines.innerHTML += "<div class='line'>" + txt + "</div>";

    linesData.push({ role: "user", content: txt });
    socket.send(JSON.stringify(linesData));
}

function opensocket(url) {
    var protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    var fullUrl = protocol + window.location.host + url;
    console.log("Intentando conectar a: " + fullUrl);

    var socket = new WebSocket(fullUrl);

    socket.addEventListener("open", (event) => {
        console.log("✅ Conexión establecida con el servidor");
    });

    socket.addEventListener("message", (event) => {
        console.log("📩 Mensaje recibido:", event.data); // Esto es vital para depurar
        processMessage(event);
    });

    socket.addEventListener("error", (event) => {
        console.error("❌ Error en el socket:", event);
    });

    socket.addEventListener("close", (event) => {
        console.log("🔌 Socket cerrado. Reintentando...");
        setTimeout(() => { opensocket(url); }, 2000);
    });

    return socket;
}

function processMessage(event) {
    let rdata = JSON.parse(event.data);

    if (rdata.action == "init_system_response") {
        loadingbar.style.display = "block";
        // Creamos un contenedor para la respuesta
        lines.innerHTML += "<div class='line server'></div>";
        linesData.push({ role: "assistant", content: "" });
    } else if (rdata.action == "append_system_response") {
        let slines = lines.querySelectorAll(".server");
        let lastLine = slines[slines.length - 1];

        // 1. Acumulamos el contenido en la memoria
        linesData[linesData.length - 1].content += rdata.content;

        // 2. Renderizamos TODO el contenido acumulado como Markdown
        // Esto permite que si una negrita se corta a la mitad (**hola),
        // se cierre correctamente cuando llegue el resto.
        lastLine.innerHTML = marked.parse(linesData[linesData.length - 1].content);

        // Autoscroll para seguir la respuesta
        var container = document.getElementById("linescontainer");
        container.scrollTop = container.scrollHeight;

    } else if (rdata.action == "finish_system_response") {
        loadingbar.style.display = "none";
    }
}