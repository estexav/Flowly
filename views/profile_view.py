import flet as ft
import asyncio
from services.firebase_service import change_password, get_account_info


class ProfileView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/profile"

        is_dark = self.page.theme_mode == ft.ThemeMode.DARK if hasattr(self.page, "theme_mode") else False
        title_color = ft.Colors.WHITE if is_dark else None

        # Datos del usuario
        self.email_text = ft.Text("", size=16, color=title_color)

        # Cambio de contraseña
        self.new_pass = ft.TextField(label="Nueva contraseña", password=True, can_reveal_password=True)
        self.confirm_pass = ft.TextField(label="Confirmar contraseña", password=True, can_reveal_password=True)
        self.msg = ft.Text("")

        self.change_btn = ft.ElevatedButton(text="Cambiar contraseña", on_click=self.on_change_password)
        self.logout_btn = ft.TextButton(text="Cerrar sesión", icon=ft.Icons.LOGOUT, on_click=self.on_logout)

        self.appbar = ft.AppBar(
            title=ft.Text("Perfil"),
            actions=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="Volver", on_click=lambda e: self.page.go("/dashboard")),
            ],
        )

        card_profile = ft.Card(
            content=ft.Container(
                padding=15,
                content=ft.Column([
                    ft.Text("Datos de la cuenta", size=20, weight=ft.FontWeight.BOLD, color=title_color),
                    ft.Row([ft.Text("Email:" , weight=ft.FontWeight.W_600, color=title_color), self.email_text]),
                ])
            )
        )

        card_password = ft.Card(
            content=ft.Container(
                padding=15,
                content=ft.Column([
                    ft.Text("Cambio de contraseña", size=20, weight=ft.FontWeight.BOLD, color=title_color),
                    self.new_pass,
                    self.confirm_pass,
                    self.change_btn,
                    self.msg,
                    ft.Divider(),
                    self.logout_btn,
                ], spacing=10)
            )
        )

        self.controls = [
            ft.Column([
                card_profile,
                card_password,
            ], expand=True, scroll=ft.ScrollMode.ADAPTIVE)
        ]

    def did_mount(self):
        # Cargar datos de perfil
        async def load():
            email = await self.page.client_storage.get_async("email")
            # Si el email no está guardado (usuarios logueados antes del cambio), intentamos resolverlo
            if not email:
                id_token = await self.page.client_storage.get_async("id_token")
                if id_token:
                    import asyncio as _asyncio
                    loop = _asyncio.get_event_loop()
                    info = await loop.run_in_executor(None, get_account_info, id_token)
                    if isinstance(info, dict) and "users" in info and info["users"]:
                        email = info["users"][0].get("email")
                        if email:
                            await self.page.client_storage.set_async("email", email)
            self.email_text.value = email or "(desconocido)"
            self.page.update()
        self.page.run_task(load)

    async def on_change_password(self, e):
        new_password = self.new_pass.value or ""
        confirm = self.confirm_pass.value or ""
        if len(new_password) < 6:
            self.msg.value = "La contraseña debe tener al menos 6 caracteres."
            self.msg.color = ft.Colors.RED_500
            self.page.update()
            return
        if new_password != confirm:
            self.msg.value = "Las contraseñas no coinciden."
            self.msg.color = ft.Colors.RED_500
            self.page.update()
            return

        id_token = await self.page.client_storage.get_async("id_token")
        if not id_token:
            self.msg.value = "No hay sesión válida. Vuelve a iniciar sesión."
            self.msg.color = ft.Colors.RED_500
            self.page.update()
            return

        self.msg.value = "Actualizando contraseña..."
        self.msg.color = ft.Colors.BLUE_500
        self.page.update()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, change_password, id_token, new_password)
        if "error" in result:
            self.msg.value = result["error"]
            self.msg.color = ft.Colors.RED_500
        else:
            self.msg.value = "Contraseña actualizada correctamente."
            self.msg.color = ft.Colors.GREEN_500
            # Actualizar token si el backend lo proporciona
            new_token = result.get("idToken")
            if new_token:
                await self.page.client_storage.set_async("id_token", new_token)
        self.page.update()

    async def on_logout(self, e):
        # Limpiar sesión y almacenamiento del cliente
        self.page.session.set("authenticated", False)
        self.page.session.set("user_id", None)
        await self.page.client_storage.set_async("is_logged_in", False)
        await self.page.client_storage.remove_async("email")
        await self.page.client_storage.remove_async("id_token")
        await self.page.client_storage.remove_async("user_id")
        # Redirigir al login
        self.page.go("/login")
