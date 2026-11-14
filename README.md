# ECSE3038 Test 2: The bathroom fan

Llamario Sinclair, ECSE3038 Engineering IoT Systems, Test 2 (13 November 2026).

An ESP32 (simulated in Wokwi) with a DHT22 humidity sensor and an LED that stands for a bathroom extractor fan, plus the Python API it talks to.

- The board POSTs its humidity to the API every 10 s, with its own `X-API-Key`.
- Someone sets the fan's mode (`auto`, `on`, `off`) and humidity limit with `PUT /fans/{mac}/settings`.
- The API stores the settings in MongoDB Atlas and publishes them, retained, on MQTT. The board subscribes and drives the LED.
- The board reports the fan on `ecse3038/llamario/fan/state` and its presence on `ecse3038/llamario/status` (with a last will).

My API runs on an Azure VM at http://iot-llamario.northcentralus.cloudapp.azure.com/docs

## Layout

- `api/`: FastAPI and MongoDB Atlas
- `board/`: the PlatformIO project for the ESP32, run in Wokwi

## Run the API

1. `cd api`
2. `python3 -m venv venv` then `source venv/bin/activate` (Windows: `venv\Scripts\activate`)
3. `python -m pip install -r requirements.txt`
4. Create a `.env` file in `api/` (never committed) with:
5. `uvicorn app:app --host 127.0.0.1 --port 8000`

Open `/docs` for the routes: `POST /fans`, `GET /fans`, `GET /fans/{mac}`, `POST /readings`, `GET /readings`, `PUT /fans/{mac}/settings`, `DELETE /fans/{mac}`.

## Run the board

1. Open the `board` folder in VS Code with PlatformIO installed.
2. Create `board/include/secrets.h` (never committed) containing `#define DEVICE_KEY ""`.
3. Build, then run Wokwi (F1, Wokwi: Start Simulator). Copy the MAC from the Serial Monitor.
4. `POST /fans` with that MAC. Put the key it returns between the quotes in `secrets.h`.
5. Build and start Wokwi again. The board now posts readings.
6. `PUT /fans/{mac}/settings` with `{"mode": "auto", "max_humidity": 65}`, then drag the DHT22's humidity above 65: the LED lights.

## MQTT topics

| Topic | Written by | Retained | Carries |
|---|---|---|---|
| `ecse3038/llamario/fan/settings` | the API (PUT) | yes | `{"mode": "auto", "max_humidity": 65.0}` |
| `ecse3038/llamario/fan/state` | the board | yes | `on` or `off` |
| `ecse3038/llamario/status` | the board and the broker (last will) | yes | `online` or `offline` |