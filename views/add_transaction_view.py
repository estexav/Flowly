import flet as ft
import datetime
from services.firebase_service import add_transaction
import asyncio
from utils.offline_store import add_pending_transaction, get_cached_transactions, set_cached_transactions

class AddTransactionView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/add_transaction"
        self.appbar = ft.AppBar(title=ft.Text("Añadir Nueva Transacción"))

        self.amount_field = ft.TextField(
            label="Monto",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_text="$",
            text_align=ft.TextAlign.RIGHT,
        )
        self.description_field = ft.TextField(label="Descripción")
        self.type_dropdown = ft.Dropdown(
            label="Tipo",
            options=[
                ft.dropdown.Option("Ingreso"),
                ft.dropdown.Option("Gasto"),
            ],
            value="Gasto",
        )
        self.date_picker = ft.DatePicker(
            on_change=self.change_date,
            on_dismiss=self.date_picker_dismissed,
            first_date=datetime.datetime(2023, 1, 1),
            last_date=datetime.datetime(2027, 12, 31),
        )
        self.page.overlay.append(self.date_picker)

        self.selected_date_text = ft.Text(value=datetime.date.today().strftime("%Y-%m-%d"))
        self.date_button = ft.IconButton(
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=lambda _: (setattr(self.date_picker, 'open', True), self.page.update()),
        )

        self.category_dropdown = ft.Dropdown(
            label="Categoría",
            options=[
                ft.dropdown.Option("Alimentación"),
                ft.dropdown.Option("Transporte"),
                ft.dropdown.Option("Vivienda"),
                ft.dropdown.Option("Servicios"),
                ft.dropdown.Option("Entretenimiento"),
                ft.dropdown.Option("Salud"),
                ft.dropdown.Option("Educación"),
                ft.dropdown.Option("Compras"),
                ft.dropdown.Option("Impuestos"),
                ft.dropdown.Option("Deudas"),
                ft.dropdown.Option("Otros"),
            ],
            value="Alimentación",
        )
        self.message_text = ft.Text("", color=ft.Colors.RED_500)

        self.save_button = ft.ElevatedButton("Guardar Transacción", on_click=self.save_transaction)
        self.cancel_button = ft.ElevatedButton("Cancelar", on_click=lambda e: self.page.go("/dashboard"))

        self.controls = [
            ft.Column(
                [
                    ft.Text("Añadir Nueva Transacción", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    self.amount_field,
                    self.description_field,
                    self.type_dropdown,
                    ft.Row(
                        [
                            self.date_button,
                            self.selected_date_text,
                        ],
                        alignment=ft.MainAxisAlignment.START
                    ),
                    self.category_dropdown,
                    self.message_text,
                    ft.Row(
                        [
                            self.save_button,
                            self.cancel_button,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.START,
                expand=True,
            )
        ]

    def change_date(self, e):
        if self.date_picker.value:
            self.selected_date_text.value = self.date_picker.value.strftime("%Y-%m-%d")
        self.page.update()

    def date_picker_dismissed(self, e):
        print(f"Date picker dismissed: {self.date_picker.value}")
        if self.page:
            self.page.update()

    async def save_transaction(self, e):
        if not getattr(self, "page", None):
            return
        user_id = self.page.session.get("user_id")
        if not user_id:
            self.message_text.value = "Error: Usuario no autenticado."
            self.message_text.color = ft.Colors.RED_500
            self.page.update()
            return

        try:
            amount = float(self.amount_field.value)
            if amount <= 0:
                raise ValueError("El monto debe ser mayor que cero.")
        except ValueError as ve:
            self.message_text.value = f"Error en el monto: {ve}"
            self.message_text.color = ft.Colors.RED_500
            self.page.update()
            return

        description = self.description_field.value
        if not description:
            self.message_text.value = "La descripción no puede estar vacía."
            self.message_text.color = ft.Colors.RED_500
            self.page.update()
            return

        transaction_type = self.type_dropdown.value
        transaction_date = self.selected_date_text.value
        category = self.category_dropdown.value if self.category_dropdown.value else "Otros"

        transaction_data = {
            "amount": amount,
            "description": description,
            "type": transaction_type,
            "date": transaction_date,
            "category": category,
            "timestamp": datetime.datetime.now().isoformat()
        }

        self.message_text.value = "Guardando transacción..."
        self.message_text.color = ft.Colors.BLUE_500
        self.page.update()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, add_transaction, user_id, transaction_data)

        if "error" in result:
            # Guardar en cola local para sincronizar cuando haya conexión
            if getattr(self, "page", None):
                await add_pending_transaction(self.page, user_id, transaction_data)
            # Actualizar caché local para que aparezca en la UI offline
            if getattr(self, "page", None):
                cached = await get_cached_transactions(self.page, user_id)
                cached.append(transaction_data)
                await set_cached_transactions(self.page, user_id, cached)

            self.message_text.value = "Sin conexión: guardado en local. Se sincronizará al volver la red."
            self.message_text.color = ft.Colors.ORANGE_700
            self.page.update()
        else:
            # Éxito: actualizar caché (para que el dashboard se refresque sin esperar)
            if getattr(self, "page", None):
                cached = await get_cached_transactions(self.page, user_id)
                transaction_data_with_id = dict(transaction_data)
                transaction_data_with_id["id"] = result.get("id")
                cached.append(transaction_data_with_id)
                await set_cached_transactions(self.page, user_id, cached)

            self.message_text.value = "Transacción guardada exitosamente!"
            self.message_text.color = ft.Colors.GREEN_500
            self.page.update()
            await asyncio.sleep(1)
            self.page.go("/dashboard")
