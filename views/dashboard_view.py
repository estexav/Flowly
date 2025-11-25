import flet as ft
from services.firebase_service import get_user_transactions
import asyncio
from utils.calculations import calculate_transaction_summary
from utils.offline_store import get_cached_transactions, set_cached_transactions, sync_pending_transactions

class DashboardView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/dashboard"
        self._mounted = False
        self.transactions = []
        self.transactions_list_view = ft.ListView(expand=1, spacing=10, auto_scroll=True)
        # Filtros
        self.type_filter = ft.Dropdown(
            label="Tipo",
            options=[ft.dropdown.Option("Todos"), ft.dropdown.Option("Ingreso"), ft.dropdown.Option("Gasto")],
            value="Todos",
            on_change=self.on_filter_change,
            width=180,
        )
        self.category_filter = ft.Dropdown(
            label="Categoría",
            options=[ft.dropdown.Option("Todas")],
            value="Todas",
            on_change=self.on_filter_change,
            width=220,
        )
        self.appbar = ft.AppBar(
            title=ft.Text("FLOWLY"),
            actions=[]
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
                    ft.Row([self.type_filter, self.category_filter], alignment=ft.MainAxisAlignment.START),
                    self.transactions_list_view,

                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.START,
                expand=True, # Make the column expand to fill available space
                scroll=ft.ScrollMode.ADAPTIVE # Enable scrolling for the column
            )
        ]
    def did_mount(self):
        self._mounted = True
        self.page.run_task(self.load_transactions)

    def will_unmount(self):
        self._mounted = False

    def add_transaction_click(self, e):
        self.page.go("/add_transaction")

    async def load_transactions(self):
        if not getattr(self, "page", None) or not self._mounted:
            return
        user_id = self.page.session.get("user_id")
        if user_id:
            loop = asyncio.get_event_loop()
            try:
                self.transactions = await loop.run_in_executor(None, get_user_transactions, user_id)
                # Cachear última versión para uso offline
                if getattr(self, "page", None) and self._mounted:
                    await set_cached_transactions(self.page, user_id, self.transactions)
            except Exception:
                # Fallback: usar caché local si la carga remota falla
                if getattr(self, "page", None):
                    self.transactions = await get_cached_transactions(self.page, user_id)
            # Actualizar opciones de categorías a partir de datos
            categories = sorted({t.get('category', 'Otros') for t in self.transactions if isinstance(t.get('category'), str)})
            if not categories:
                categories = ["Alimentación","Transporte","Vivienda","Servicios","Entretenimiento","Salud","Educación","Compras","Impuestos","Deudas","Otros"]
            self.category_filter.options = [ft.dropdown.Option("Todas")] + [ft.dropdown.Option(c) for c in categories]
            if self.category_filter.value not in (['Todas'] + categories):
                self.category_filter.value = "Todas"

            # Aplicar filtros y refrescar UI
            self.apply_filters()

            if getattr(self, "page", None) and self._mounted:
                self.page.update()
            # Intentar sincronización de pendientes en segundo plano
            if getattr(self, "page", None) and self._mounted:
                asyncio.create_task(sync_pending_transactions(self.page, user_id))

    def on_filter_change(self, e):
        self.apply_filters()
        if getattr(self, "page", None) and self._mounted:
            self.page.update()

    def apply_filters(self):
        # Filtrar por tipo y categoría y re-renderizar lista y totales
        type_sel = self.type_filter.value
        cat_sel = self.category_filter.value
        filtered = []
        for t in self.transactions:
            if type_sel != "Todos" and t.get('type') != type_sel:
                continue
            if cat_sel != "Todas" and t.get('category', 'Otros') != cat_sel:
                continue
            filtered.append(t)

        self.transactions_list_view.controls.clear()
        if filtered:
            for transaction in filtered:
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
                                    ft.Text(
                                        f"Fecha: {transaction.get('date', 'N/A')} • {transaction.get('category', 'Otros')}",
                                        size=12,
                                        color=ft.Colors.GREY_600,
                                    ),
                                ]
                            ),
                            padding=10,
                            on_click=lambda e, transaction_id=transaction.get('id'): self.page.go(f"/edit_transaction/{transaction_id}")
                        ),
                        elevation=2,
                    )
                )
        else:
            self.transactions_list_view.controls.append(ft.Text("No hay transacciones para mostrar con los filtros actuales."))

        total_income, total_expenses, total_balance = calculate_transaction_summary(filtered)
        self.total_balance_text.value = f"Saldo Total: ${total_balance:.2f}"
        self.total_income_text.value = f"Ingresos del Mes: ${total_income:.2f}"
        self.total_expenses_text.value = f"Gastos del Mes: ${total_expenses:.2f}"

    # Cerrar sesión se gestiona ahora desde ProfileView
