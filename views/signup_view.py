import flet as ft
from services.firebase_service import signup_user
import asyncio

class SignupView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/signup"
        self.appbar = ft.AppBar(title=ft.Text("Registrarse"))
        self.email_field = ft.TextField(label="Email")
        self.password_field = ft.TextField(label="Contraseña", password=True, can_reveal_password=True)
        self.message_text = ft.Text("", color=ft.Colors.RED_500)
        self.signup_button = ft.ElevatedButton("Registrarse", on_click=self.signup_new_user)
        self.login_button = ft.TextButton("¿Ya tienes cuenta? Inicia Sesión", on_click=self.go_to_login)
        self.controls = [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Crear una cuenta", size=24),
                        self.email_field,
                        self.password_field,
                        self.message_text,
                        self.signup_button,
                        self.login_button,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True
                ),
                expand=True,
                padding=20
            )
        ]

    async def signup_new_user(self, e):
        email = self.email_field.value
        password = self.password_field.value

        if not email or not password:
            self.message_text.value = "Por favor, ingresa tu email y contraseña."
            self.page.update()
            return

        self.message_text.value = "Registrando usuario..."
        self.message_text.color = ft.Colors.BLUE_500
        self.page.update()

        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, signup_user, email, password)
        result = await future

        if "error" in result:
            self.message_text.value = result["error"]
            self.message_text.color = ft.Colors.RED_500
        else:
            self.message_text.value = "¡Registro exitoso! Redirigiendo a inicio de sesión..."
            self.message_text.color = ft.Colors.GREEN_500
            await self.page.update_async()
            await self.page.go_async("/login")
        self.page.update()

    def go_to_login(self, e):
        print("Ir a la página de inicio de sesión")
        self.page.go("/login")
