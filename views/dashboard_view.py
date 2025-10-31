import flet as ft
from services.firebase_service import get_user_transactions
import asyncio
from utils.calculations import calculate_transaction_summary

class DashboardView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/dashboard"
        self.transactions = []
        self.transactions_list_view = ft.ListView(expand=1, spacing=10, auto_scroll=True)
        self.appbar = ft.AppBar(
            title=ft.Text("FLOWLY"),
            actions=[
                ft.IconButton(
                    icon=ft.Icons.LOGOUT,
                    on_click=self.logout,
                    tooltip="Cerrar Sesión",
                )
            ]
        )

        self.total_balance_text = ft.Text("Saldo Total: $0.00", size=36, weight=ft.FontWeight.BOLD)
        self.total_income_text = ft.Text("Ingresos del Mes: $0.00", size=16, color=ft.Colors.GREEN_700)
        self.total_expenses_text = ft.Text("Gastos del Mes: $0.00", size=16, color=ft.Colors.RED_700)

        self.controls = [
            ft.Column(
                [
                    ft.Text("Bienvenido a tu App de Finanzas", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Text("Resumen de Saldos", size=20, weight=ft.FontWeight.BOLD),
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column(
                                [
                                    self.total_balance_text,
                                    self.total_income_text,
                                    self.total_expenses_text,
                                ]
                            ),
                            padding=15,
                        ),
                        elevation=5,
                    ),
                    ft.Divider(),
                    ft.Text("Transacciones Recientes", size=20, weight=ft.FontWeight.BOLD),
                    self.transactions_list_view,

                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.START,
                expand=True, # Make the column expand to fill available space
                scroll=ft.ScrollMode.ADAPTIVE # Enable scrolling for the column
            )
        ]
        self.page.run_task(self.load_transactions)

    def add_transaction_click(self, e):
        self.page.go("/add_transaction")

    async def load_transactions(self):
        user_id = self.page.session.get("user_id")
        if user_id:
            loop = asyncio.get_event_loop()
            self.transactions = await loop.run_in_executor(None, get_user_transactions, user_id)
            self.transactions_list_view.controls.clear()

            if self.transactions:
                for transaction in self.transactions:
                    amount = transaction.get('amount', 0.0)
                    transaction_type = transaction.get('type')
                    self.transactions_list_view.controls.append(
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            f"{transaction.get('description', 'N/A')} - ${amount:.2f}",
                                            size=16,
                                            color=ft.Colors.GREEN_500 if transaction_type == 'Ingreso' else ft.Colors.RED_500
                                        ),
                                        ft.Text(f"Fecha: {transaction.get('date', 'N/A')}", size=12, color=ft.Colors.GREY_600),
                                    ]
                                ),
                                padding=10,
                                on_click=lambda e, transaction_id=transaction.get('id'): self.page.go(f"/edit_transaction/{transaction_id}")
                            ),
                            elevation=2,
                        )
                    )
            else:
                self.transactions_list_view.controls.append(ft.Text("No hay transacciones para mostrar."))

            total_income, total_expenses, total_balance = calculate_transaction_summary(self.transactions)

            self.total_balance_text.value = f"Saldo Total: ${total_balance:.2f}"
            self.total_income_text.value = f"Ingresos del Mes: ${total_income:.2f}"
            self.total_expenses_text.value = f"Gastos del Mes: ${total_expenses:.2f}"

            self.page.update()

    async def logout(self, e):
        self.page.session.set("authenticated", False)
        self.page.session.set("user_id", None)
        await self.page.client_storage.set_async("is_logged_in", False)
        await self.page.client_storage.remove_async("user_id")
        self.page.go("/login")