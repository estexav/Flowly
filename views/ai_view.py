import os
import flet as ft
import asyncio
from services.firebase_service import get_user_transactions
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
                chat_card,
                pred_card,
                ft.Container(height=80),  # espacio inferior
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
            # Mostrar loader temporal encima del chat
            self.chat_list.controls.clear()
            self.chat_list.controls.append(self.loader_container)
            self.page.update()
            loop = asyncio.get_event_loop()
            try:
                self.transactions = await loop.run_in_executor(None, get_user_transactions, user_id)
                if getattr(self, "page", None) and self._mounted:
                    await set_cached_transactions(self.page, user_id, self.transactions)
            except Exception:
                if getattr(self, "page", None):
                    self.transactions = await get_cached_transactions(self.page, user_id)
            # Cargar predicción inicial
            try:
                pred = predict_spending(self.transactions)
                summary = pred.get("summary", {})
                self.pred_summary_text.value = (
                    f"Resumen: ingresos ${summary.get('incomes', 0):.2f}, "
                    f"gastos ${summary.get('expenses', 0):.2f}, "
                    f"disponible ${summary.get('disposable', 0):.2f}"
                )
                # Actualizar métricas
                self.incomes_text.value = f"${summary.get('incomes', 0):.2f}"
                self.expenses_text.value = f"${summary.get('expenses', 0):.2f}"
                self.disposable_text.value = f"${summary.get('disposable', 0):.2f}"
                by_cat = summary.get("by_category", {})
                suggested = pred.get("suggested_budget", {})
                rows = []
                for cat, current in by_cat.items():
                    rows.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(cat)),
                        ft.DataCell(ft.Text(f"${current:.2f}", text_align=ft.TextAlign.RIGHT)),
                        ft.DataCell(ft.Text(f"${suggested.get(cat, current):.2f}", text_align=ft.TextAlign.RIGHT)),
                    ]))
                self.pred_table.rows = rows or []
                # Color dinámico para disponible
                try:
                    disp_val = float(summary.get("disposable", 0))
                except Exception:
                    disp_val = 0.0
                if self._is_dark():
                    self.disposable_text.color = ft.Colors.GREEN_300 if disp_val >= 0 else ft.Colors.RED_300
                else:
                    self.disposable_text.color = ft.Colors.GREEN_900 if disp_val >= 0 else ft.Colors.RED_900
                # Barras de distribución
                total = max(summary.get("expenses", 0.0), 1.0)
                bars = []
                for cat, val in by_cat.items():
                    ratio = float(val) / float(total)
                    bars.append(
                        ft.Row([
                            ft.Text(cat, width=140, color=(ft.Colors.WHITE if self._is_dark() else None)),
                            ft.Container(
                                content=ft.ProgressBar(value=ratio, bgcolor=ft.Colors.GREY_800 if self._is_dark() else ft.Colors.GREY_200, color=ft.Colors.BLUE_300 if self._is_dark() else ft.Colors.BLUE_600),
                                width=300,
                                height=12,
                                border_radius=6,
                            ),
                            ft.Text(f"{ratio*100:.0f}%", width=60, text_align=ft.TextAlign.RIGHT, color=(ft.Colors.WHITE if self._is_dark() else None)),
                        ], alignment=ft.MainAxisAlignment.START)
                    )
                self.pred_bars.controls = bars
                # Mostrar consejo en panel
                self.pred_advice.value = pred.get("advice", "")
                # Mensaje inicial en el chat
                self.add_assistant_bubble("Hola, soy tu asistente financiero. ¿En qué te ayudo hoy?")
            except Exception:
                pass
            self._loading = False
            # Ocultar loader si está presente
            try:
                self.chat_list.controls.remove(self.loader_container)
            except ValueError:
                # Si ya no existe, continuar sin error
                pass
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
