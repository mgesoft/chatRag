# test_ollama.py
import httpx
import asyncio


async def test_ollama():
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # Probar endpoint de modelos
            resp = await client.get("http://ollama:11434/api/tags")
            print(f" Modelos disponibles: {resp.json().get('models', [])}")

            # Probar generación simple
            resp = await client.post(
                "http://ollama:11434/api/generate",
                json={"model": "phi3", "prompt": "Hola, responde en una palabra", "stream": False},
                timeout=60
            )
            print(f" Respuesta: {resp.json().get('response', 'N/A')[:100]}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_ollama())