import firebase_admin
from firebase_admin import credentials, firestore, auth
import requests
import json
import os
import tempfile
from pathlib import Path

# Initialize Firebase Admin SDK (server-side operations)
project_root = Path(__file__).resolve().parents[1]

# Orden de carga de credenciales:
# 1) FIREBASE_SERVICE_ACCOUNT_JSON (contenido completo del JSON en variable de entorno)
# 2) GOOGLE_APPLICATION_CREDENTIALS (ruta a archivo de credenciales)
# 3) Fallback local: credentials.json en la raíz del proyecto
service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
env_cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

if service_account_json:
    tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json")
    tmp.write(service_account_json)
    tmp.close()
    cred = credentials.Certificate(tmp.name)
elif env_cred_path and Path(env_cred_path).exists():
    cred = credentials.Certificate(env_cred_path)
else:
    service_account_path = project_root / "credentials.json"
    if not service_account_path.exists():
        raise RuntimeError("No se encontraron credenciales de Firebase: define env o añade credentials.json en la raíz.")
    cred = credentials.Certificate(str(service_account_path))

firebase_admin.initialize_app(cred)

db = firestore.client()

# Firebase Web API Key for client-side authentication (usa env si está disponible, o el valor por defecto para pruebas)
FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY", "AIzaSyBomKn6eLpmV-dREWDqQklKuHwWUBPNTOI")

def signup_user(email, password):
    """Registers a new user with email and password using Firebase Auth REST API."""
    rest_api_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}"
    payload = json.dumps({
        "email": email,
        "password": password,
        "returnSecureToken": True
    })
    try:
        r = requests.post(rest_api_url, data=payload)
        r.raise_for_status() # Raise an exception for HTTP errors
        return r.json()
    except requests.exceptions.RequestException as e:
        print(f"Error during signup: {e}")
        if r.status_code == 400:
            error_data = r.json().get("error", {})
            message = error_data.get("message", "Unknown error")
            if message == "EMAIL_EXISTS":
                return {"error": "El correo electrónico ya está registrado."}
            elif message == "WEAK_PASSWORD : Password should be at least 6 characters":
                return {"error": "La contraseña debe tener al menos 6 caracteres."}
            else:
                return {"error": f"Error de Firebase: {message}"}
        return {"error": "Error de conexión o servidor."}

def login_user(email, password):
    """Logs in an existing user with email and password using Firebase Auth REST API."""
    rest_api_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
    payload = json.dumps({
        "email": email,
        "password": password,
        "returnSecureToken": True
    })
    try:
        r = requests.post(rest_api_url, data=payload)
        r.raise_for_status() # Raise an exception for HTTP errors
        return r.json()
    except requests.exceptions.RequestException as e:
        print(f"Error during login: {e}")
        if r.status_code == 400:
            error_data = r.json().get("error", {})
            message = error_data.get("message", "Unknown error")
            if message == "EMAIL_NOT_FOUND":
                return {"error": "El correo electrónico no está registrado."}
            elif message == "INVALID_PASSWORD":
                return {"error": "Contraseña incorrecta."}
            elif message == "USER_DISABLED":
                return {"error": "El usuario ha sido deshabilitado."}
            else:
                return {"error": f"Error de Firebase: {message}"}
        return {"error": "Error de conexión o servidor."}

def get_firestore_client():
    return db

def get_auth_client():
    return auth_client

def get_user_transactions(user_id):
    """Retrieves all transactions for a given user ID from Firestore."""
    transactions_ref = db.collection("transactions")
    query = transactions_ref.where(filter=firestore.FieldFilter("userId", "==", user_id)).stream()
    transactions = []
    for doc in query:
        transaction_data = doc.to_dict()
        transaction_data["id"] = doc.id  # Add document ID to the transaction data
        transactions.append(transaction_data)
    return transactions

def add_transaction(user_id, transaction_data):
    """Adds a new transaction for a given user ID to Firestore."""
    transaction_data["userId"] = user_id
    try:
        doc_ref = db.collection("transactions").add(transaction_data)
        return {"success": True, "id": doc_ref[1].id}
    except Exception as e:
        print(f"Error adding transaction: {e}")
        return {"error": str(e)}

def get_transaction_by_id(transaction_id):
    """Retrieves a single transaction by its ID from Firestore."""
    try:
        doc_ref = db.collection("transactions").document(transaction_id).get()
        if doc_ref.exists:
            transaction_data = doc_ref.to_dict()
            transaction_data["id"] = doc_ref.id
            return transaction_data
        else:
            return None
    except Exception as e:
        print(f"Error getting transaction by ID: {e}")
        return None

def update_transaction(transaction_id, updated_data):
    """Updates an existing transaction in Firestore."""
    try:
        db.collection("transactions").document(transaction_id).update(updated_data)
        return {"success": True}
    except Exception as e:
        print(f"Error updating transaction: {e}")
        return {"error": str(e)}

def delete_transaction(transaction_id):
    """Deletes a transaction from Firestore."""
    try:
        db.collection("transactions").document(transaction_id).delete()
        return {"success": True}
    except Exception as e:
        print(f"Error deleting transaction: {e}")
        return {"error": str(e)}
