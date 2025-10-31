import flet as ft
from services.firebase_service import login_user, signup_user # Importar las nuevas funciones
import asyncio

class LoginView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/login"
        self.appbar = ft.AppBar(title=ft.Text("Iniciar Sesión"))
        self.email_field = ft.TextField(label="Email")
        self.password_field = ft.TextField(label="Contraseña", password=True, can_reveal_password=True)
        self.message_text = ft.Text("", color=ft.Colors.RED_500) # Nuevo control para mensajes
        self.login_button = ft.ElevatedButton("Iniciar Sesión", on_click=self.login_user)
        self.signup_button = ft.TextButton("¿No tienes cuenta? Regístrate", on_click=self.go_to_signup)
        self.controls = [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Bienvenidos", size=24),
                        self.email_field,
                        self.password_field,
                        self.message_text,
                        self.login_button,
                        self.signup_button,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True
                ),
                expand=True,
                padding=20
            )
        ]

    async def login_user(self, e):
        email = self.email_field.value
        password = self.password_field.value
        
        if not email or not password:
            self.message_text.value = "Por favor, ingresa tu email y contraseña."
            self.page.update()
            return

        self.message_text.value = "Iniciando sesión..."
        self.message_text.color = ft.Colors.BLUE_500
        self.page.update()

        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, login_user, email, password)
        result = await future
        
        if "error" in result:
            self.message_text.value = result["error"]
            self.message_text.color = ft.Colors.RED_500
        else:
            self.message_text.value = "¡Inicio de sesión exitoso! Redirigiendo..."
            self.message_text.color = ft.Colors.GREEN_500
            self.page.session.set("authenticated", True)
            self.page.session.set("user_id", result["localId"])
            await self.page.client_storage.set_async("is_logged_in", True)
            await self.page.client_storage.set_async("user_id", result["localId"])
            self.page.go("/dashboard")

    def go_to_signup(self, e):
        print("Ir a la página de registro")
        self.page.go("/signup") # Redirigir a la página de registro
