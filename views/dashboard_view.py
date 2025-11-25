import flet as ft
from services.firebase_service import get_user_transactions, get_user_recurrings
import asyncio
from utils.calculations import calculate_transaction_summary
from utils.offline_store import get_cached_transactions, set_cached_transactions, sync_pending_transactions
import datetime

class DashboardView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/dashboard"
        self._mounted = False
        self.transactions = []
        self.recurrings = []

        self.type_filter = ft.Dropdown(
            label="Tipo",
            options=[ft.dropdown.Option("Todos"), ft.dropdown.Option("Ingreso"), ft.dropdown.Option("Gasto")],
            value="Todos",
            on_change=self.on_filter_change,
            width=220,
        )
        self.category_filter = ft.Dropdown(
            label="Categoría",
            options=[ft.dropdown.Option("Todas")],
            value="Todas",
            on_change=self.on_filter_change,
            width=260,
        )

        self.appbar = ft.AppBar(title=ft.Text("FLOWLY"), actions=[])

        self.income_card = self._metric_card("Ingresos", ft.Icons.TRENDING_UP, ft.Colors.GREEN_700, "$0.00", "Total del mes")
        self.expense_card = self._metric_card("Gastos", ft.Icons.TRENDING_DOWN, ft.Colors.RED_700, "$0.00", "Total del mes")
        self.balance_card = self._metric_card("Balance", ft.Icons.RECEIPT_LONG, ft.Colors.BLUE_700, "$0.00", "Ahorro")

        self.normal_radius = 100
        self.hover_radius = 110
        self.normal_title_style = ft.TextStyle(size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
        self.hover_title_style = ft.TextStyle(size=16, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.BLACK54))

        self.pie_chart = ft.PieChart(sections=[], sections_space=0, center_space_radius=40, on_chart_event=self.on_chart_event, expand=True)
        self.bar_chart = ft.Container(height=280)

        self.category_details = ft.Column(spacing=12)

        self.controls = [
            ft.Column(
                [
                    ft.Row(
                        [self.income_card, self.expense_card, self.balance_card],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        expand=True,
                    ),
                    ft.Row(
                        [
                            ft.Card(content=ft.Container(content=ft.Column([ft.Text("Gastos por Categoría", weight=ft.FontWeight.BOLD), self.pie_chart]), padding=16), elevation=4, expand=1),
                            ft.Card(content=ft.Container(content=ft.Column([ft.Text("Comparación Mensual", weight=ft.FontWeight.BOLD), self.bar_chart]), padding=16), elevation=4, expand=1),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([ft.Text("Detalle por Categoría", weight=ft.FontWeight.BOLD), self.category_details]),
                            padding=16,
                        ),
                        elevation=4,
                    ),
                ],
                expand=True,
                scroll=ft.ScrollMode.ADAPTIVE,
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
                self.recurrings = await loop.run_in_executor(None, get_user_recurrings, user_id)
                # Cachear última versión para uso offline
                if getattr(self, "page", None) and self._mounted:
                    await set_cached_transactions(self.page, user_id, self.transactions)
            except Exception:
                if getattr(self, "page", None):
                    from utils.offline_store import get_cached_recurrings
                    self.transactions = await get_cached_transactions(self.page, user_id)
                    self.recurrings = await get_cached_recurrings(self.page, user_id)
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
        type_sel = self.type_filter.value
        cat_sel = self.category_filter.value
        filtered = []
        for t in self.transactions:
            if type_sel != "Todos" and t.get('type') != type_sel:
                continue
            if cat_sel != "Todas" and t.get('category', 'Otros') != cat_sel:
                continue
            filtered.append(t)

        def monthly_equiv(amount: float, freq: str) -> float:
            f = (freq or "Mensual").lower()
            if f.startswith("semanal"):
                return amount * 4.33
            if f.startswith("quincenal"):
                return amount * 2.0
            if f.startswith("mensual"):
                return amount
            if f.startswith("bimestral"):
                return amount / 2.0
            if f.startswith("trimestral"):
                return amount / 3.0
            if f.startswith("anual"):
                return amount / 12.0
            return amount
        for r in self.recurrings or []:
            amt = monthly_equiv(float(r.get("amount", 0.0) or 0.0), r.get("frequency", "Mensual"))
            if type_sel != "Todos" and r.get("type") != type_sel:
                continue
            if cat_sel != "Todas" and r.get("category", "Otros") != cat_sel:
                continue
            filtered.append({
                "amount": amt,
                "type": r.get("type", "Gasto"),
                "category": r.get("category", "Recurrente"),
                "description": r.get("description", "Recurrente"),
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            })

        self._update_metrics(filtered)
        self._update_charts(filtered)
        self._update_category_details(filtered)

    def on_chart_event(self, e: ft.PieChartEvent):
        for idx, section in enumerate(self.pie_chart.sections):
            if idx == e.section_index:
                section.radius = self.hover_radius
                section.title_style = self.hover_title_style
            else:
                section.radius = self.normal_radius
                section.title_style = self.normal_title_style
        self.pie_chart.update()

    def _metric_card(self, title: str, icon: str, color: str, amount_text: str, subtitle: str) -> ft.Card:
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([ft.Text(title, weight=ft.FontWeight.BOLD), ft.Icon(icon)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(amount_text, size=24, weight=ft.FontWeight.BOLD),
                    ft.Text(subtitle, size=12),
                ]),
                padding=16,
                bgcolor=color,
                border_radius=12,
            ),
            elevation=3,
            expand=1,
        )

    def _update_metrics(self, filtered):
        incomes = sum(float(t.get('amount', 0.0)) for t in filtered if t.get('type') == 'Ingreso')
        expenses = sum(float(t.get('amount', 0.0)) for t in filtered if t.get('type') == 'Gasto')
        balance = incomes - expenses
        self.income_card.content.content.controls[1].value = f"${incomes:.2f}"
        self.expense_card.content.content.controls[1].value = f"${expenses:.2f}"
        self.balance_card.content.content.controls[1].value = f"${balance:.2f}"

    def _update_charts(self, filtered):
        by_cat = {}
        for t in filtered:
            transaction_type = t.get('type')
            category = t.get('category', 'Sin Categoría')
            amount = float(t.get('amount', 0.0))
            if transaction_type == 'Gasto':
                by_cat[category] = by_cat.get(category, 0.0) + amount
        incomes = sum(float(t.get('amount', 0.0)) for t in filtered if t.get('type') == 'Ingreso')
        expenses = sum(float(t.get('amount', 0.0)) for t in filtered if t.get('type') == 'Gasto')

        colors = [
            ft.Colors.BLUE_ACCENT_700, ft.Colors.GREEN_ACCENT_700, ft.Colors.RED_ACCENT_700,
            ft.Colors.PURPLE_ACCENT_700, ft.Colors.ORANGE_ACCENT_700, ft.Colors.TEAL_ACCENT_700,
            ft.Colors.CYAN_ACCENT_700, ft.Colors.PINK_ACCENT_700, ft.Colors.LIME_ACCENT_700,
            ft.Colors.INDIGO_ACCENT_700, ft.Colors.BROWN_700, ft.Colors.DEEP_ORANGE_700,
            ft.Colors.LIGHT_BLUE_700, ft.Colors.LIGHT_GREEN_700, ft.Colors.AMBER_700
        ]
        sections = []
        color_index = 0
        for category_name, amount in by_cat.items():
            sections.append(
                ft.PieChartSection(
                    value=amount,
                    title=f"{category_name} (${amount:.2f})",
                    color=colors[color_index % len(colors)],
                    radius=self.normal_radius,
                    title_style=self.normal_title_style,
                )
            )
            color_index += 1
        self.pie_chart.sections = sections

        total = incomes + expenses
        total = total if total > 0 else 1.0
        self.bar_chart.content = ft.Column([
            ft.Row([ft.Text("Ingresos"), ft.Text(f"${incomes:.2f}")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.ProgressBar(value=incomes/total),
            ft.Row([ft.Text("Gastos"), ft.Text(f"${expenses:.2f}")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.ProgressBar(value=expenses/total),
        ])

    def _update_category_details(self, filtered):
        by_cat = {}
        for t in filtered:
            c = t.get('category', 'Otros')
            amt = float(t.get('amount', 0.0))
            if t.get('type') == 'Gasto':
                by_cat[c] = by_cat.get(c, 0.0) + amt
        total = sum(by_cat.values()) or 1.0
        self.category_details.controls.clear()
        for c, v in sorted(by_cat.items(), key=lambda x: x[1], reverse=True):
            self.category_details.controls.append(
                ft.Row([
                    ft.Text(c),
                    ft.Text(f"${v:.2f}"),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
            self.category_details.controls.append(ft.ProgressBar(value=v/total))

    # Cerrar sesión se gestiona ahora desde ProfileView
