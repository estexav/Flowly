import os
try:
    import onesignal
    from onesignal.api import default_api
    from onesignal.model.notification import Notification
    _ONESIGNAL_AVAILABLE = True
except Exception:
    # Evita que la app crashee si el paquete 'onesignal' no está instalado
    _ONESIGNAL_AVAILABLE = False

# Reemplaza estos con tus claves REALES de OneSignal
ONESIGNAL_APP_ID = "bc1f92fd-7604-4354-a7e6-6885c36fc741"  
ONESIGNAL_APP_KEY = "https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js"
ONESIGNAL_USER_KEY = "le8lVRRuZJYzRSexSM2ApI04HnT2" # Opcional si solo usas la REST API KEY

class OnesignalNotifications:
    def __init__(self):
        self.available = _ONESIGNAL_AVAILABLE
        if self.available:
            configuration = onesignal.Configuration(
                app_key=ONESIGNAL_USER_KEY,  # Puede requerirse la User Auth Key
                rest_api_key=ONESIGNAL_APP_KEY,
            )
            self.api_client = onesignal.ApiClient(configuration)
            self.api_instance = default_api.DefaultApi(self.api_client)
        else:
            self.api_client = None
            self.api_instance = None

    def createNotification(self, onesignal_id):
        if not self.available:
            return None
        notification = Notification()
        notification.app_id = ONESIGNAL_APP_ID
        notification.contents = {"en": "¡Tienes una nueva notificación de Flowly!"}
        notification.include_external_user_ids = [onesignal_id]
        return notification

    def send(self, onesignal_id):
        if not self.available:
            print("⚠️ OneSignal SDK no disponible. Saltando envío de notificación.")
            return None
        try:
            notification = self.createNotification(onesignal_id)
            notification_response = self.api_instance.create_notification(notification)
            print(f"✅ Notificación enviada. Respuesta de OneSignal: {notification_response}")
            return notification_response
        except Exception as e:
            print(f"❌ Error al enviar notificación: {e}")
            return None
        finally:
            try:
                if self.api_client:
                    self.api_client.close()
            except Exception:
                pass
