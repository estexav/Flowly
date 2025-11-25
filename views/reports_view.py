import flet as ft
from services.firebase_service import get_user_transactions, get_user_recurrings
import asyncio
from utils.offline_store import get_cached_transactions, set_cached_transactions, sync_pending_transactions
import math
from datetime import datetime, date

class ReportsView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/reports"
        self.transactions = []
        self.recurrings = []
        self._mounted = False

        self.appbar = ft.AppBar(
            title=ft.Text("Informes"),
            actions=[ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: self.page.go("/dashboard"), tooltip="Volver")],
        )

        self.balance_text = ft.Text("$0.00", size=24, weight=ft.FontWeight.BOLD)
        self.incomes_month_text = ft.Text("$0.00", size=24, weight=ft.FontWeight.BOLD)
        self.fixed_month_text = ft.Text("$0.00", size=24, weight=ft.FontWeight.BOLD)
        self.savings_month_text = ft.Text("$0.00", size=24, weight=ft.FontWeight.BOLD)

        self.spend_input = ft.TextField(label="Monto del Gasto", prefix_text="$", keyboard_type=ft.KeyboardType.NUMBER, value="200")
        self.calc_btn = ft.FilledButton(text="Calcular", icon=ft.Icons.CALCULATE, on_click=self.on_calculate)
        self.spend_result = ft.Container(padding=12, border_radius=8)
        self.impact_rows = ft.Column(spacing=6)

        self.goal_input = ft.TextField(label="Meta de Ahorro", prefix_text="$", keyboard_type=ft.KeyboardType.NUMBER, value="5000")
        self.goal_date_picker = ft.DatePicker(first_date=date(datetime.now().year, 1, 1), last_date=date(datetime.now().year + 5, 12, 31), on_change=self.on_goal_date_change)
        self.page.overlay.append(self.goal_date_picker)
        self.goal_date_text = ft.Text(value=datetime.now().strftime("%d/%m/%Y"))
        self.goal_date_btn = ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, on_click=lambda e: self.open_goal_date())
        self.goal_progress = ft.ProgressBar(value=0.0)
        self.goal_result = ft.Container(padding=12, border_radius=8)
        self.goal_details = ft.Column(spacing=6)
        self.suggestions = ft.Column(spacing=4)

        header_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Tu Situación Financiera", size=20, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.Column([ft.Text("Balance"), self.balance_text], expand=1),
                        ft.Column([ft.Text("Ingresos/mes"), self.incomes_month_text], expand=1),
                        ft.Column([ft.Text("Gastos Fijos"), self.fixed_month_text], expand=1),
                        ft.Column([ft.Text("Ahorro/mes"), self.savings_month_text], expand=1),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ]),
                padding=16,
                bgcolor=ft.Colors.DEEP_PURPLE_400,
                border_radius=12,
            ),
            elevation=4,
        )

        left_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("¿Puedo Permitirme Este Gasto?", size=18, weight=ft.FontWeight.BOLD),
                    ft.Row([self.spend_input], alignment=ft.MainAxisAlignment.START),
                    self.calc_btn,
                    self.spend_result,
                    ft.Text("Análisis del Impacto", size=16, weight=ft.FontWeight.BOLD),
                    self.impact_rows,
                ]),
                padding=16,
            ),
            elevation=4,
            expand=1,
        )

        right_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Proyección de Meta de Ahorro", size=18, weight=ft.FontWeight.BOLD),
                    ft.Row([self.goal_input], alignment=ft.MainAxisAlignment.START),
                    ft.Row([self.goal_date_text, self.goal_date_btn], alignment=ft.MainAxisAlignment.START),
                    ft.Text("Progreso Proyectado"),
                    self.goal_progress,
                    self.goal_result,
                    self.goal_details,
                    ft.Text("Sugerencias:", size=16, weight=ft.FontWeight.BOLD),
                    self.suggestions,
                ]),
                padding=16,
            ),
            elevation=4,
            expand=1,
        )

        self.controls = [
            ft.Column([
                header_card,
                ft.Row([left_card, right_card], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], expand=True, scroll=ft.ScrollMode.ADAPTIVE)
        ]

    def did_mount(self):
        self._mounted = True
        self.page.run_task(self.load_reports)

    def will_unmount(self):
        self._mounted = False

    def on_chart_event(self, e: ft.PieChartEvent):
        for idx, section in enumerate(self.pie_chart.sections):
            if idx == e.section_index:
                section.radius = self.hover_radius
                section.title_style = self.hover_title_style
            else:
                section.radius = self.normal_radius
                section.title_style = self.normal_title_style
        self.pie_chart.update()

    async def load_reports(self):
        if not getattr(self, "page", None) or not self._mounted:
            return
        user_id = self.page.session.get("user_id")
        if user_id:
            loop = asyncio.get_event_loop()
            try:
                self.transactions = await loop.run_in_executor(None, get_user_transactions, user_id)
                self.recurrings = await loop.run_in_executor(None, get_user_recurrings, user_id)
                if getattr(self, "page", None) and self._mounted:
                    await set_cached_transactions(self.page, user_id, self.transactions)
            except Exception:
                if getattr(self, "page", None):
                    from utils.offline_store import get_cached_recurrings
                    self.transactions = await get_cached_transactions(self.page, user_id)
                    self.recurrings = await get_cached_recurrings(self.page, user_id)

            incomes_m, expenses_m, fixed_m, savings_m, balance_m = self._compute_metrics()
            self.balance_text.value = f"${balance_m:.2f}"
            self.incomes_month_text.value = f"${incomes_m:.2f}"
            self.fixed_month_text.value = f"${fixed_m:.2f}"
            self.savings_month_text.value = f"${savings_m:.2f}"

            if getattr(self, "page", None) and self._mounted:
                self.page.update()
            if getattr(self, "page", None) and self._mounted:
                asyncio.create_task(sync_pending_transactions(self.page, user_id))

    def _compute_metrics(self):
        now = datetime.now()
        m = now.month
        y = now.year
        incomes = 0.0
        expenses = 0.0
        fixed = 0.0
        fixed_cats = {"Vivienda", "Servicios", "Impuestos", "Deudas"}
        for t in self.transactions:
            try:
                dt = datetime.strptime(t.get("date", now.strftime("%Y-%m-%d")), "%Y-%m-%d")
            except Exception:
                dt = now
            if dt.month == m and dt.year == y:
                amt = float(t.get("amount", 0.0) or 0.0)
                if t.get("type") == "Ingreso":
                    incomes += amt
                elif t.get("type") == "Gasto":
                    expenses += amt
                    if t.get("category", "Otros") in fixed_cats:
                        fixed += amt

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
            if r.get("type") == "Ingreso":
                incomes += amt
            else:
                expenses += amt
                fixed += amt
        savings = incomes - expenses
        balance = max(savings, 0.0)
        return incomes, expenses, fixed, savings, balance

    def on_calculate(self, e):
        try:
            spend = float(self.spend_input.value or 0.0)
        except Exception:
            spend = 0.0
        incomes_m, expenses_m, fixed_m, savings_m, balance_m = self._compute_metrics()
        new_balance = max(savings_m - spend, 0.0)
        perc = (spend / incomes_m) if incomes_m > 0 else 0.0
        margin = new_balance - fixed_m
        status = "Seguro" if perc <= 0.03 else ("Procede con Precaución" if perc <= 0.08 else "No recomendado")
        bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN) if status == "Seguro" else (ft.Colors.with_opacity(0.12, ft.Colors.ORANGE) if status == "Procede con Precaución" else ft.Colors.with_opacity(0.12, ft.Colors.RED))
        border_c = ft.Colors.GREEN_300 if status == "Seguro" else (ft.Colors.ORANGE_300 if status == "Procede con Precaución" else ft.Colors.RED_300)
        self.spend_result.bgcolor = bg
        self.spend_result.border = ft.border.all(2, border_c)
        self.spend_result.content = ft.Column([
            ft.Row([ft.Icon(ft.Icons.WARNING_AMBER), ft.Text(status, weight=ft.FontWeight.BOLD)], spacing=8),
            ft.Text(f"Puedes hacer este gasto, representa el {perc*100:.1f}% de tus ingresos." if status != "No recomendado" else f"Este gasto representa el {perc*100:.1f}% de tus ingresos, considera reducirlo."),
        ], spacing=6)
        self.impact_rows.controls = [
            ft.Row([ft.Text("Balance actual"), ft.Text(f"${balance_m:.2f}")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Después del gasto"), ft.Text(f"${new_balance:.2f}")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Gastos fijos a cubrir"), ft.Text(f"${fixed_m:.2f}")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Margen de seguridad"), ft.Text(f"${max(margin,0.0):.2f}", color=(ft.Colors.GREEN_400 if margin>=0 else ft.Colors.RED_400))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ]
        if getattr(self, "page", None) and self._mounted:
            self.page.update()

    def on_goal_date_change(self, e):
        if self.goal_date_picker.value:
            self.goal_date_text.value = self.goal_date_picker.value.strftime("%d/%m/%Y")
        self._recalc_goal()

    def open_goal_date(self):
        self.goal_date_picker.open = True
        if getattr(self, "page", None):
            self.page.update()

    def _recalc_goal(self):
        try:
            goal_amt = float(self.goal_input.value or 0.0)
        except Exception:
            goal_amt = 0.0
        incomes_m, expenses_m, fixed_m, savings_m, balance_m = self._compute_metrics()
        target = self.goal_date_picker.value or datetime.now().date()
        now_d = datetime.now().date()
        months = max((target.year - now_d.year) * 12 + (target.month - now_d.month), 1)
        need_pm = goal_amt / months if months > 0 else goal_amt
        proj_total = savings_m * months
        pct = min(savings_m / need_pm, 1.0) if need_pm > 0 else 1.0
        self.goal_progress.value = pct
        if savings_m >= need_pm:
            msg = ft.Text("Meta alcanzable", weight=ft.FontWeight.BOLD)
            bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN)
            border_c = ft.Colors.GREEN_300
        else:
            deficit = max(need_pm - savings_m, 0.0)
            msg = ft.Text(f"Meta difícil: necesitas ${need_pm:.2f}/mes, faltan ${deficit:.2f}/mes", weight=ft.FontWeight.BOLD)
            bg = ft.Colors.with_opacity(0.12, ft.Colors.ORANGE)
            border_c = ft.Colors.ORANGE_300
        self.goal_result.bgcolor = bg
        self.goal_result.border = ft.border.all(2, border_c)
        self.goal_result.content = ft.Row([ft.Icon(ft.Icons.WARNING_AMBER), msg], spacing=8)
        self.goal_details.controls = [
            ft.Row([ft.Text("Ahorro mensual necesario"), ft.Text(f"${need_pm:.2f}")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Ahorro mensual actual"), ft.Text(f"${savings_m:.2f}", color=ft.Colors.GREEN_400)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Meses hasta objetivo"), ft.Text(str(months))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Proyección total"), ft.Text(f"${proj_total:.2f}", color=(ft.Colors.GREEN_400 if proj_total>=goal_amt else ft.Colors.ORANGE_400))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ]
        suggs = []
        if savings_m < need_pm:
            delta = need_pm - savings_m
            suggs.append(f"Reduce gastos variables por ${delta:.2f}/mes")
            suggs.append(f"Busca ingresos adicionales por ${delta:.2f}/mes")
            suggs.append("Extiende la fecha objetivo si es necesario")
        else:
            suggs.append("Vas por buen camino, mantén el ritmo de ahorro")
        self.suggestions.controls = [ft.Row([ft.Text(f"• {s}")]) for s in suggs]
        if getattr(self, "page", None) and self._mounted:
            self.page.update()
