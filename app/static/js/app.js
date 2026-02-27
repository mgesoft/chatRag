let socket = new WebSocket('ws://' + window.location.host + '/init');
let lines = document.getElementById("lines"); // Asegúrate que este ID existe en tu HTML
let linesData = [];

socket.onmessage = function(event) {
    let rdata = JSON.parse(event.data);
    console.log("Mensaje recibido:", rdata); // Para que veas en F12 si llega algo

    if (rdata.action == "init_system_response") {
        // Creamos un nuevo div para la respuesta
        let newDiv = document.createElement("div");
        newDiv.className = "line server";
        lines.appendChild(newDiv);
        linesData.push({ role: "assistant", content: "" });
    }
    else if (rdata.action == "append_system_response") {
        let serverDivs = document.querySelectorAll(".server");
        let lastDiv = serverDivs[serverDivs.length - 1];

        // Acumulamos el contenido
        linesData[linesData.length - 1].content += rdata.content;
        // Lo mostramos (puedes usar .innerText para empezar)
        lastDiv.innerText = linesData[linesData.length - 1].content;

        // Scroll automático al final
        window.scrollTo(0, document.body.scrollHeight);
    }
    else if (rdata.action == "finish_system_response") {
        console.log("Respuesta terminada");
    }
};

// Función para enviar mensajes
function sendMessage() {
    let input = document.getElementById("user-input");
    if (input.value.trim() !== "") {
        let message = input.value;
        // Dibujamos el mensaje del usuario en pantalla
        lines.innerHTML += `<div class="line user">${message}</div>`;

        // Enviamos al servidor como el historial que espera
        let history = [{ role: "user", content: message }];
        socket.send(JSON.stringify(history));

        input.value = "";
    }
}