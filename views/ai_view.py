import os
import flet as ft
import asyncio
import datetime
import calendar
from services.firebase_service import get_user_transactions, get_user_recurrings
from utils.offline_store import get_cached_transactions, set_cached_transactions, sync_pending_transactions
from services.finance_ai_api import chat_finance, predict_spending, quick_prompt_response


class AIView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/ai"
        self._mounted = False
        self.transactions = []
        self._loading = False

        def _is_dark():
            try:
                return self.page.theme_mode == ft.ThemeMode.DARK
            except Exception:
                return False
        self._is_dark = _is_dark

        # Estado IA
        ia_active = (os.getenv("GEMINI_API_KEY") or "").strip() != ""
        chip_bg = (
            ft.Colors.with_opacity(0.18, ft.Colors.GREEN) if (ia_active and self._is_dark()) else (
                ft.Colors.GREEN_50 if ia_active else (
                    ft.Colors.with_opacity(0.18, ft.Colors.GREY) if self._is_dark() else ft.Colors.GREY_100
                )
            )
        )
        chip_text_color = ft.Colors.WHITE if self._is_dark() else None
        self.ia_chip = ft.Chip(
            label=ft.Text("IA activa" if ia_active else "IA (modo heurístico)", color=chip_text_color),
            bgcolor=chip_bg,
            leading=ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.GREEN_300 if self._is_dark() else (ft.Colors.GREEN_600 if ia_active else ft.Colors.GREY_600))
        )

        # Chat (solo respuestas de chips)
        self.chat_list = ft.ListView(expand=1, spacing=10, auto_scroll=True)

        # Quick prompts
        self.quick_prompts = ft.Row(
            [
                ft.FilledTonalButton(text="Resumen mensual", on_click=lambda e: self.on_quick_prompt("¿Cuál es mi resumen mensual?")),
                ft.FilledTonalButton(text="Recortes", on_click=lambda e: self.on_quick_prompt("¿Dónde recortar gastos sin impactar mucho?")),
                ft.FilledTonalButton(text="Comprar algo", on_click=lambda e: self.on_quick_prompt("Quiero comprar algo, ¿cuánto puedo gastar seguro?")),
                ft.FilledTonalButton(text="Presupuesto semanal", on_click=lambda e: self.on_quick_prompt("Sugiere un presupuesto semanal por categoría")),
            ],
            wrap=True,
            spacing=10,
        )

        # Predicción
        # Métricas destacadas
        self.incomes_text = ft.Text("$0.00", size=16, weight=ft.FontWeight.BOLD, color=(ft.Colors.GREEN_300 if self._is_dark() else ft.Colors.GREEN_900))
        self.expenses_text = ft.Text("$0.00", size=16, weight=ft.FontWeight.BOLD, color=(ft.Colors.RED_300 if self._is_dark() else ft.Colors.RED_900))
        self.disposable_text = ft.Text("$0.00", size=16, weight=ft.FontWeight.BOLD, color=(ft.Colors.BLUE_GREY_100 if self._is_dark() else None))

        # Atenuar fondos en oscuro para evitar deslumbramiento
        income_bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN) if self._is_dark() else ft.Colors.GREEN_50
        expense_bg = ft.Colors.with_opacity(0.12, ft.Colors.RED) if self._is_dark() else ft.Colors.RED_50
        dispo_bg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_GREY) if self._is_dark() else ft.Colors.BLUE_GREY_50

        label_color = ft.Colors.WHITE if self._is_dark() else None
        self.metrics_row = ft.Row([
            ft.Container(content=ft.Column([ft.Text("Ingresos", color=label_color), self.incomes_text]), padding=10, bgcolor=income_bg, border_radius=8, border=ft.border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.GREEN))),
            ft.Container(content=ft.Column([ft.Text("Gastos", color=label_color), self.expenses_text]), padding=10, bgcolor=expense_bg, border_radius=8, border=ft.border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.RED))),
            ft.Container(content=ft.Column([ft.Text("Disponible", color=label_color), self.disposable_text]), padding=10, bgcolor=dispo_bg, border_radius=8, border=ft.border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.BLUE_GREY))),
        ], spacing=10)

        self.pred_summary_text = ft.Text("Resumen: ingresos $0.00, gastos $0.00, disponible $0.00", color=(ft.Colors.WHITE if self._is_dark() else None))
        # Aumentar contraste del encabezado de la tabla en modo oscuro
        heading_color = ft.Colors.BLACK54 if self._is_dark() else ft.Colors.BLUE_GREY_50
        self.pred_table = ft.DataTable(columns=[
            ft.DataColumn(ft.Text("Categoría", color=(ft.Colors.WHITE if self._is_dark() else None))),
            ft.DataColumn(ft.Text("Gasto actual ($)", text_align=ft.TextAlign.RIGHT, color=(ft.Colors.WHITE if self._is_dark() else None))),
            ft.DataColumn(ft.Text("Presupuesto sugerido ($)", text_align=ft.TextAlign.RIGHT, color=(ft.Colors.WHITE if self._is_dark() else None))),
        ], rows=[], heading_row_color=heading_color)

        # Barras de distribución
        self.pred_bars_header = ft.Text("Distribución actual", size=16, weight=ft.FontWeight.BOLD, color=(ft.Colors.WHITE if self._is_dark() else None))
        self.pred_bars = ft.Column([], spacing=6)
        self.pred_advice = ft.Text(value="", selectable=True, color=(ft.Colors.WHITE if self._is_dark() else None))
        self.pred_advice_panel = ft.ExpansionTile(
            title=ft.Text("Consejos y recomendaciones"),
            controls=[ft.Container(content=self.pred_advice, padding=ft.padding.only(bottom=8))]
        )

        ia_status = "Activa" if ia_active else "Heurística"
        self.appbar = ft.AppBar(
            title=ft.Text(f"Asistente de IA"),
            actions=[
                self.ia_chip,
                ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="Volver", on_click=lambda e: self.page.go("/dashboard")),
            ],
        )

        self.balance_value = ft.Text("$0.00", size=16, weight=ft.FontWeight.BOLD, color=(ft.Colors.GREEN_300 if self._is_dark() else ft.Colors.GREEN_900))
        self.daily_avg_value = ft.Text("$0.00", size=16, weight=ft.FontWeight.BOLD)
        self.autonomy_chip = ft.Chip(label=ft.Text("0 días"))
        self.next_income_date = ft.Text("")
        self.next_income_amount = ft.Text("$0.00")

        self.pb_30 = ft.ProgressBar(value=0.0)
        self.pb_60 = ft.ProgressBar(value=0.0)
        self.pb_90 = ft.ProgressBar(value=0.0)
        self.s30_text = ft.Text("$0.00", color=ft.Colors.GREEN_300 if self._is_dark() else ft.Colors.GREEN_900)
        self.s60_text = ft.Text("$0.00", color=ft.Colors.GREEN_300 if self._is_dark() else ft.Colors.GREEN_900)
        self.s90_text = ft.Text("$0.00", color=ft.Colors.GREEN_300 if self._is_dark() else ft.Colors.GREEN_900)

        self.recurring_list = ft.Column(spacing=8)
        self.advice_text = ft.Text("", selectable=True)

        status_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE), ft.Text("Estado financiero")], alignment=ft.MainAxisAlignment.START, spacing=8),
                    ft.Row([ft.Text("Balance actual"), self.balance_value], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ]),
                padding=15,
            ),
            elevation=4,
        )

        actual_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Estado Actual", size=18, weight=ft.FontWeight.BOLD),
                    ft.Row([ft.Text("Balance actual"), self.balance_value], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Gasto diario promedio"), self.daily_avg_value], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Días de autonomía"), self.autonomy_chip], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Próximo ingreso esperado"), self.next_income_date], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Monto estimado"), self.next_income_amount], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ]),
                padding=15,
            ),
            elevation=4,
            expand=1,
        )

        projection_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Proyección de Ahorro", size=18, weight=ft.FontWeight.BOLD),
                    ft.Row([ft.Text("En 30 días"), self.s30_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.pb_30,
                    ft.Row([ft.Text("En 60 días"), self.s60_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.pb_60,
                    ft.Row([ft.Text("En 90 días"), self.s90_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.pb_90,
                ]),
                padding=15,
            ),
            elevation=4,
            expand=1,
        )

        recurrent_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Gastos Recurrentes Detectados", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("Estos gastos se repiten regularmente. Presupuesta para ellos."),
                    self.recurring_list,
                ]),
                padding=15,
            ),
            elevation=4,
        )

        advice_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Consejos Inteligentes", size=18, weight=ft.FontWeight.BOLD),
                    self.advice_text,
                ]),
                padding=15,
            ),
            elevation=4,
        )

        # Layout con tarjetas
        chat_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Chat Financiero", size=20, weight=ft.FontWeight.BOLD),
                    self.quick_prompts,
                    ft.Container(content=self.chat_list, height=280, padding=ft.padding.only(top=5)),
                ]),
                padding=15,
            ),
            elevation=5,
        )
        pred_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Predicción de Gastos (próximo mes)", size=20, weight=ft.FontWeight.BOLD),
                    self.metrics_row,
                    self.pred_summary_text,
                    self.pred_table,
                    self.pred_bars_header,
                    self.pred_bars,
                    self.pred_advice_panel,
                ]),
                padding=15,
            ),
            elevation=5,
        )

        self.loader = ft.Row([ft.ProgressRing(), ft.Text("Cargando datos...", color=(ft.Colors.WHITE if self._is_dark() else None))], alignment=ft.MainAxisAlignment.CENTER)
        self.loader_container = ft.Container(content=self.loader, padding=10)

        # Mantener scroll de la columna y añadir un spacer inferior para evitar solape con la barra
        self.controls = [
            ft.Column([
                status_card,
                ft.Row([actual_card, projection_card], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                recurrent_card,
                advice_card,
                chat_card,
                ft.Container(height=60),
            ], expand=True, scroll=ft.ScrollMode.ADAPTIVE)
        ]

    def did_mount(self):
        self._mounted = True
        self.page.run_task(self.load_data)

    def will_unmount(self):
        self._mounted = False

    async def load_data(self):
        if not getattr(self, "page", None) or not self._mounted:
            return
        user_id = self.page.session.get("user_id")
        if user_id:
            self._loading = True
            loop = asyncio.get_event_loop()
            try:
                recs = []
                self.transactions = await loop.run_in_executor(None, get_user_transactions, user_id)
                recs = await loop.run_in_executor(None, get_user_recurrings, user_id)
                if getattr(self, "page", None) and self._mounted:
                    await set_cached_transactions(self.page, user_id, self.transactions)
            except Exception:
                if getattr(self, "page", None):
                    from utils.offline_store import get_cached_recurrings
                    self.transactions = await get_cached_transactions(self.page, user_id)
                    recs = await get_cached_recurrings(self.page, user_id)
            try:
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
                synth = []
                for r in recs or []:
                    amt = monthly_equiv(float(r.get("amount", 0.0) or 0.0), r.get("frequency", "Mensual"))
                    synth.append({
                        "amount": amt,
                        "type": r.get("type", "Gasto"),
                        "category": r.get("category", "Recurrente"),
                        "description": r.get("description", "Recurrente"),
                        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                    })
                tx_for_pred = list(self.transactions) + synth
                pred = predict_spending(tx_for_pred)
                summary = pred.get("summary", {})
                incomes = float(summary.get("incomes", 0.0) or 0.0)
                expenses = float(summary.get("expenses", 0.0) or 0.0)
                disposable = float(summary.get("disposable", 0.0) or 0.0)
                self.balance_value.value = f"${disposable:.2f}"
                daily_avg = (expenses / 30.0) if expenses > 0 else 0.0
                self.daily_avg_value.value = f"${daily_avg:.2f}"
                autonomy_days = int(disposable / daily_avg) if daily_avg > 0 else 0
                self.autonomy_chip.label = ft.Text(f"{autonomy_days} días")
                now = datetime.datetime.now()
                nm = (now.month % 12) + 1
                ny = now.year + (1 if now.month == 12 else 0)
                self.next_income_date.value = f"1 {calendar.month_name[nm][:3].lower()}"
                self.next_income_amount.value = f"${incomes:.2f}"

                s30 = max(disposable, 0.0)
                s60 = s30 * 2
                s90 = s30 * 3
                mx = max(s90, 1.0)
                self.s30_text.value = f"+${s30:.2f}"
                self.s60_text.value = f"+${s60:.2f}"
                self.s90_text.value = f"+${s90:.2f}"
                self.pb_30.value = s30 / mx
                self.pb_60.value = s60 / mx
                self.pb_90.value = s90 / mx

                by_cat = summary.get("by_category", {})
                self.recurring_list.controls = []
                for cat, val in sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:5]:
                    self.recurring_list.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Column([ft.Text(cat, weight=ft.FontWeight.BOLD), ft.Text(f"Promedio: ${val:.2f} • Frecuencia: 1x")], expand=True),
                                ft.Container(content=ft.Text(f"${val:.2f}"), padding=ft.padding.only(left=12, right=12, top=6, bottom=6), border_radius=16, bgcolor=ft.Colors.DEEP_PURPLE_400),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            padding=8,
                            border_radius=8,
                        )
                    )

                self.advice_text.value = pred.get("advice", "")
            except Exception:
                pass
            self._loading = False
            if getattr(self, "page", None) and self._mounted:
                self.page.update()
            if getattr(self, "page", None) and self._mounted:
                asyncio.create_task(sync_pending_transactions(self.page, user_id))

    def on_chat_send(self, e):
        # Deshabilitado: solo se permite interacción mediante chips.
        return

    def add_user_bubble(self, text: str):
        is_dark = self._is_dark()
        user_bg = ft.Colors.with_opacity(0.16, ft.Colors.AMBER) if is_dark else ft.Colors.AMBER_50
        user_border = ft.Colors.with_opacity(0.25, ft.Colors.AMBER) if is_dark else ft.Colors.AMBER_200
        text_color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK
        self.chat_list.controls.append(
            ft.Row([
                ft.Container(
                    content=ft.Text(text, color=text_color),
                    padding=10,
                    bgcolor=user_bg,
                    border_radius=8,
                    border=ft.border.all(1, user_border),
                    width=500,
                )
            ], alignment=ft.MainAxisAlignment.END)
        )

    def add_assistant_bubble(self, text: str):
        is_dark = self._is_dark()
        as_bg = ft.Colors.with_opacity(0.18, ft.Colors.BLUE_GREY) if is_dark else ft.Colors.BLUE_GREY_50
        as_border = ft.Colors.with_opacity(0.25, ft.Colors.BLUE_GREY) if is_dark else ft.Colors.BLUE_GREY_100
        text_color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK
        self.chat_list.controls.append(
            ft.Row([
                ft.Container(
                    content=ft.Text(text, color=text_color),
                    padding=10,
                    bgcolor=as_bg,
                    border_radius=8,
                    border=ft.border.all(1, as_border),
                    width=500,
                )
            ], alignment=ft.MainAxisAlignment.START)
        )

    def on_quick_prompt(self, text: str):
        # Muestra pregunta predefinida (burbuja) y responde con lógica específica por chip
        self.add_user_bubble(text)
        mapping = {
            "¿Cuál es mi resumen mensual?": "resumen",
            "¿Dónde recortar gastos sin impactar mucho?": "recortes",
            "Quiero comprar algo, ¿cuánto puedo gastar seguro?": "comprar_algo",
            "Sugiere un presupuesto semanal por categoría": "presupuesto_semanal",
        }
        kind = mapping.get(text)
        try:
            if kind:
                reply = quick_prompt_response(kind, self.transactions)
            else:
                reply = chat_finance(text, self.transactions)
        except Exception:
            reply = "Hubo un problema generando la respuesta. Intenta de nuevo."
        self.add_assistant_bubble(reply)
        self.page.update()
