import flet as ft
import asyncio
import datetime
from services.firebase_service import get_transaction_by_id, update_transaction, delete_transaction

class EditTransactionView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/edit_transaction/:transaction_id"
        self.transaction_id = None
        self.transaction_data = None

        self.description_field = ft.TextField(label="Descripción", expand=True)
        self.amount_field = ft.TextField(label="Monto", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.type_dropdown = ft.Dropdown(
            label="Tipo",
            options=[
                ft.dropdown.Option("Ingreso"),
                ft.dropdown.Option("Gasto"),
            ],
            expand=True
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
            expand=True
        )
        self.date_picker = ft.DatePicker(
            first_date=datetime.datetime(2023, 1, 1),
            last_date=datetime.datetime(2024, 12, 31),
            on_change=self.on_date_change,
        )
        self.page.overlay.append(self.date_picker)
        self.date_button = ft.ElevatedButton(
            "Seleccionar Fecha",
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=lambda _: self.date_picker.pick_date(),
        )
        self.selected_date_text = ft.Text()

        self.appbar = ft.AppBar(
            title=ft.Text("Editar Transacción"),
            leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: self.page.go("/dashboard"))
        )

        self.controls = [
            ft.Column(
                [
                    self.description_field,
                    self.amount_field,
                    self.type_dropdown,
                    self.category_dropdown,
                    ft.Row([self.date_button, self.selected_date_text]),
                    ft.ElevatedButton("Guardar Cambios", on_click=self.save_transaction),
                    ft.ElevatedButton("Eliminar Transacción", on_click=self.delete_transaction, style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500)),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
                expand=True
            )
        ]

    def did_mount(self):
        self.transaction_id = self.page.route.split("/")[-1]
        self.page.run_task(self.load_transaction_data)

    async def load_transaction_data(self):
        if self.transaction_id:
            loop = asyncio.get_event_loop()
            self.transaction_data = await loop.run_in_executor(None, get_transaction_by_id, self.transaction_id)
            if self.transaction_data:
                self.description_field.value = self.transaction_data.get("description", "")
                self.amount_field.value = str(self.transaction_data.get("amount", 0.0))
                self.type_dropdown.value = self.transaction_data.get("type", "Ingreso")
                self.category_dropdown.value = self.transaction_data.get("category", "Otros")
                self.selected_date_text.value = self.transaction_data.get("date", "")
                self.page.update()
            else:
                print(f"Transacción con ID {self.transaction_id} no encontrada.")
                self.page.go("/dashboard")

    def on_date_change(self, e):
        if self.date_picker.value:
            self.selected_date_text.value = self.date_picker.value.strftime("%Y-%m-%d")
            self.page.update()

    def on_date_dismiss(self, e):
        print(f"Date picker dismissed, value is {self.date_picker.value}")

    async def save_transaction(self, e):
        if not self.transaction_id:
            print("No transaction ID found for saving.")
            return

        updated_data = {
            "description": self.description_field.value,
            "amount": float(self.amount_field.value),
            "type": self.type_dropdown.value,
            "category": self.category_dropdown.value or "Otros",
            "date": self.selected_date_text.value,
        }

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, update_transaction, self.transaction_id, updated_data)
        self.page.go("/dashboard")

    async def delete_transaction(self, e):
        if not self.transaction_id:
            print("No transaction ID found for deletion.")
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, delete_transaction, self.transaction_id)
        self.page.go("/dashboard")
