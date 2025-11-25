import flet as ft
import datetime
from services.firebase_service import add_transaction, add_recurring
import asyncio
from utils.offline_store import add_pending_transaction, get_cached_transactions, set_cached_transactions

class AddTransactionView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/add_transaction"
        self.appbar = ft.AppBar(title=ft.Text("Nueva Transacción"))
        self.selected_type = "Gasto"

        self.amount_field = ft.TextField(
            label="Monto",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_text="$",
            text_align=ft.TextAlign.RIGHT,
        )
        self.description_field = ft.TextField(label="Descripción", hint_text="Ej: Compra en supermercado")
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
            hint_text="Selecciona una categoría",
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

        self.recurring_switch = ft.Switch(label="Fijo recurrente", value=False, on_change=lambda e: self.on_recurring_toggle())
        self.frequency_dropdown = ft.Dropdown(
            label="Frecuencia",
            options=[
                ft.dropdown.Option("Semanal"),
                ft.dropdown.Option("Quincenal"),
                ft.dropdown.Option("Mensual"),
                ft.dropdown.Option("Bimestral"),
                ft.dropdown.Option("Trimestral"),
                ft.dropdown.Option("Anual"),
            ],
            value="Mensual",
            visible=False,
        )
        self.save_button = ft.FilledButton(text="Agregar Gasto", icon=ft.Icons.ADD_CIRCLE, on_click=self.save_transaction)
        self.cancel_button = ft.ElevatedButton("Cancelar", on_click=lambda e: self.page.go("/dashboard"))

        self.expense_toggle = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.ECO),
                ft.Text("Gasto")
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=15,
            border_radius=12,
            on_click=lambda e: self.set_type("Gasto"),
            expand=1,
        )
        self.income_toggle = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.MONETIZATION_ON),
                ft.Text("Ingreso")
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=15,
            border_radius=12,
            on_click=lambda e: self.set_type("Ingreso"),
            expand=1,
        )

        self.controls = [
            ft.Column(
                [
                    ft.Row([
                        self.expense_toggle,
                        self.income_toggle,
                    ], spacing=12),
                    ft.Row([self.recurring_switch, self.frequency_dropdown], alignment=ft.MainAxisAlignment.START),
                    self.category_dropdown,
                    self.amount_field,
                    self.description_field,
                    ft.Row([
                        self.selected_date_text,
                        self.date_button,
                    ], alignment=ft.MainAxisAlignment.START),
                    self.message_text,
                    ft.Row([
                        self.save_button,
                        self.cancel_button,
                    ], alignment=ft.MainAxisAlignment.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.START,
                expand=True,
            )
        ]
        self.apply_type_styles()

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

        transaction_type = self.selected_type
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
        if self.recurring_switch.value:
            recurring_data = {
                "amount": amount,
                "description": description,
                "type": transaction_type,
                "category": category,
                "frequency": self.frequency_dropdown.value or "Mensual",
                "start_date": transaction_date,
                "active": True,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            result = await loop.run_in_executor(None, add_recurring, user_id, recurring_data)
        else:
            result = await loop.run_in_executor(None, add_transaction, user_id, transaction_data)

        if "error" in result:
            if getattr(self, "page", None):
                if self.recurring_switch.value:
                    from utils.offline_store import get_cached_recurrings, set_cached_recurrings
                    cached_r = await get_cached_recurrings(self.page, user_id)
                    recurring_data = {
                        "amount": amount,
                        "description": description,
                        "type": transaction_type,
                        "category": category,
                        "frequency": self.frequency_dropdown.value or "Mensual",
                        "start_date": transaction_date,
                        "active": True,
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                    cached_r.append(recurring_data)
                    await set_cached_recurrings(self.page, user_id, cached_r)
                else:
                    await add_pending_transaction(self.page, user_id, transaction_data)
                    cached = await get_cached_transactions(self.page, user_id)
                    cached.append(transaction_data)
                    await set_cached_transactions(self.page, user_id, cached)

            self.message_text.value = "Sin conexión: guardado en local. Se sincronizará al volver la red."
            self.message_text.color = ft.Colors.ORANGE_700
            self.page.update()
        else:
            if getattr(self, "page", None):
                if self.recurring_switch.value:
                    from utils.offline_store import get_cached_recurrings, set_cached_recurrings
                    cached_r = await get_cached_recurrings(self.page, user_id)
                    r_with_id = {
                        "amount": amount,
                        "description": description,
                        "type": transaction_type,
                        "category": category,
                        "frequency": self.frequency_dropdown.value or "Mensual",
                        "start_date": transaction_date,
                        "active": True,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "id": result.get("id"),
                    }
                    cached_r.append(r_with_id)
                    await set_cached_recurrings(self.page, user_id, cached_r)
                else:
                    cached = await get_cached_transactions(self.page, user_id)
                    transaction_data_with_id = dict(transaction_data)
                    transaction_data_with_id["id"] = result.get("id")
                    cached.append(transaction_data_with_id)
                    await set_cached_transactions(self.page, user_id, cached)
            self.message_text.value = "Transacción guardada exitosamente!" if not self.recurring_switch.value else "Gasto fijo guardado"
            self.message_text.color = ft.Colors.GREEN_500
            self.page.update()
            await asyncio.sleep(1)
            self.page.go("/dashboard")

    def set_type(self, t: str):
        self.selected_type = t
        self.apply_type_styles()
        if getattr(self, "page", None):
            self.page.update()

    def apply_type_styles(self):
        if self.selected_type == "Gasto":
            self.expense_toggle.bgcolor = ft.Colors.with_opacity(0.22, ft.Colors.RED)
            self.expense_toggle.border = ft.border.all(2, ft.Colors.RED_300)
            self.income_toggle.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_GREY)
            self.income_toggle.border = ft.border.all(2, ft.Colors.with_opacity(0.25, ft.Colors.BLUE_GREY))
            self.save_button.text = "Agregar Gasto"
            self.save_button.bgcolor = ft.Colors.RED_700
        else:
            self.income_toggle.bgcolor = ft.Colors.with_opacity(0.22, ft.Colors.GREEN)
            self.income_toggle.border = ft.border.all(2, ft.Colors.GREEN_300)
            self.expense_toggle.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_GREY)
            self.expense_toggle.border = ft.border.all(2, ft.Colors.with_opacity(0.25, ft.Colors.BLUE_GREY))
            self.save_button.text = "Agregar Ingreso"
            self.save_button.bgcolor = ft.Colors.GREEN_700

    def on_recurring_toggle(self):
        self.frequency_dropdown.visible = bool(self.recurring_switch.value)
        if getattr(self, "page", None):
            self.page.update()
