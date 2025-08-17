from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import json

app = FastAPI()

# Ollama API endpoint
OLLAMA_API_URL = "http://localhost:11434/api/generate"

class ChatRequest(BaseModel):
    prompt: str

@app.post("/api/v1/chat")
async def chat(chat_request: ChatRequest):
    try:
        if not chat_request.prompt:
            raise HTTPException(status_code=400, detail="Prompt is missing")

        # Payload for the Ollama API
        ollama_payload = {
            "model": "smollm2:1.7b",
            "prompt": chat_request.prompt,
            "stream": False  # We want the full response at once
        }

        # Query the Ollama server
        response = requests.post(OLLAMA_API_URL, json=ollama_payload)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Extract the response content
        response_data = response.json()
        ai_response = response_data.get("response", "Sorry, I could not get a response from Ollama.")

        return {"response": ai_response}

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Could not connect to Ollama service: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)

