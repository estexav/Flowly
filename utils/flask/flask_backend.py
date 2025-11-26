from flask import Flask, make_response, jsonify, request
import json
import os

app = Flask(__name__)

# Ruta del archivo para simular la base de datos
DATA_FILE = 'onesignal_ids.json'

@app.route("/register", methods=['POST'])
def store_onesignal_id():
    """Recibe y almacena el mapeo entre user_id y onesignal_id."""
    data = request.json
    if not data or 'onesignal_id' not in data or 'user_id' not in data:
        responseObject = {'error': 'Bad request, missing IDs'}
        return make_response(jsonify(responseObject)), 400
    
    onesignal_id = data['onesignal_id']
    user_id = data['user_id']
    
    # Simular base de datos: Cargar datos existentes o un diccionario vacío
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            id_map = json.load(f)
    else:
        id_map = {}
        
    # Almacenar el mapeo: Key=user_id, Value=onesignal_id
    id_map[user_id] = onesignal_id
    
    with open(DATA_FILE, 'w') as f:
        json.dump(id_map, f, indent=4)
    
    responseObject = {"message": f"Onesignal ID saved for user {user_id}."}
    return make_response(jsonify(responseObject)), 200

if __name__ == "__main__":
    # IMPORTANTE: Usar un puerto diferente al de Flet.
    # También necesitarás habilitar CORS si el backend y Flet están en diferentes dominios/puertos.
    app.run(debug=True, host="0.0.0.0", port=5010)