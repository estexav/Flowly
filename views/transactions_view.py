import flet as ft
import asyncio
from services.firebase_service import get_user_transactions, delete_transaction, get_user_recurrings, delete_recurring
from utils.offline_store import get_cached_transactions, set_cached_transactions, sync_pending_transactions


class TransactionsView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/transactions"
        self._mounted = False
        self.transactions = []
        self.recurrings = []
        self.view_mode = "transactions"

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
        self.clear_filters_btn = ft.IconButton(icon=ft.Icons.CLEAR_ALL, tooltip="Limpiar filtros", on_click=self.reset_filters)

        self.appbar = ft.AppBar(
            title=ft.Text("Transacciones"),
            actions=[],
        )

        self.list_view = ft.ListView(expand=1, spacing=10, auto_scroll=True)
        self.rec_list = ft.ListView(expand=1, spacing=10, auto_scroll=True)

        self.mode_row = ft.Row([
            ft.FilledTonalButton(text="Transacciones", on_click=lambda e: self.set_mode("transactions")),
            ft.FilledTonalButton(text="Fijos", on_click=lambda e: self.set_mode("recurrings")),
        ], spacing=8)

        self.controls = [
            ft.Column(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Transacciones", size=20, weight=ft.FontWeight.BOLD),
                                ft.Row(
                                    [
                                        ft.Container(content=self.type_filter, width=220),
                                        ft.Container(content=self.category_filter, width=260),
                                    ],
                                    alignment=ft.MainAxisAlignment.START,
                                ),
                                self.mode_row,
                                self.list_view,
                                self.rec_list,
                            ],
                            expand=True,
                        ),
                        padding=15,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.START,
                expand=True,
                scroll=ft.ScrollMode.ADAPTIVE,
            )
        ]

    def did_mount(self):
        self._mounted = True
        self.page.run_task(self.load_transactions)

    def will_unmount(self):
        self._mounted = False

    async def load_transactions(self):
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
                    self.transactions = await get_cached_transactions(self.page, user_id)
                    try:
                        from utils.offline_store import get_cached_recurrings
                        self.recurrings = await get_cached_recurrings(self.page, user_id)
                    except Exception:
                        self.recurrings = []

            categories = sorted({t.get("category", "Otros") for t in (self.transactions + self.recurrings) if isinstance(t.get("category"), str)})
            if not categories:
                categories = [
                    "Alimentación",
                    "Transporte",
                    "Vivienda",
                    "Servicios",
                    "Entretenimiento",
                    "Salud",
                    "Educación",
                    "Compras",
                    "Impuestos",
                    "Deudas",
                    "Otros",
                ]
            self.category_filter.options = [ft.dropdown.Option("Todas")] + [ft.dropdown.Option(c) for c in categories]
            if self.category_filter.value not in (["Todas"] + categories):
                self.category_filter.value = "Todas"

            self.apply_filters()
            if getattr(self, "page", None) and self._mounted:
                self.page.update()
            if getattr(self, "page", None) and self._mounted:
                asyncio.create_task(sync_pending_transactions(self.page, user_id))

    def on_filter_change(self, e):
        self.apply_filters()
        if getattr(self, "page", None) and self._mounted:
            self.page.update()

    def reset_filters(self, e):
        try:
            self.type_filter.value = "Todos"
            self.category_filter.value = "Todas"
            self.apply_filters()
            if getattr(self, "page", None) and self._mounted:
                self.page.update()
        except Exception:
            pass

    def apply_filters(self):
        type_sel = self.type_filter.value
        cat_sel = self.category_filter.value
        tx_filtered = []
        for t in self.transactions:
            if type_sel != "Todos" and t.get("type") != type_sel:
                continue
            if cat_sel != "Todas" and t.get("category", "Otros") != cat_sel:
                continue
            tx_filtered.append(t)
        rec_filtered = []
        for r in self.recurrings:
            if type_sel != "Todos" and r.get("type") != type_sel:
                continue
            if cat_sel != "Todas" and r.get("category", "Otros") != cat_sel:
                continue
            rec_filtered.append(r)

        self.list_view.visible = self.view_mode == "transactions"
        self.rec_list.visible = self.view_mode == "recurrings"
        self.list_view.controls.clear()
        self.rec_list.controls.clear()
        if self.view_mode == "transactions":
            if tx_filtered:
                for t in tx_filtered:
                    self.list_view.controls.append(self._transaction_card(t))
            else:
                self.list_view.controls.append(ft.Text("No hay transacciones para mostrar con los filtros actuales."))
        else:
            if rec_filtered:
                for r in rec_filtered:
                    self.rec_list.controls.append(self._recurring_card(r))
            else:
                self.rec_list.controls.append(ft.Text("No hay fijos para mostrar con los filtros actuales."))

    def _is_dark(self) -> bool:
        return self.page and self.page.theme_mode == ft.ThemeMode.DARK

    def _category_chip(self, name: str) -> ft.Chip:
        is_dark = self._is_dark()
        bg = ft.Colors.BLUE_GREY_50 if not is_dark else ft.Colors.with_opacity(0.18, ft.Colors.BLUE_GREY)
        text_color = ft.Colors.WHITE if is_dark else None
        return ft.Chip(label=ft.Text(name, color=text_color), bgcolor=bg)

    def _transaction_card(self, t: dict) -> ft.Card:
        amount = float(t.get("amount", 0.0) or 0.0)
        ttype = t.get("type", "Gasto")
        icon = ft.Icons.TRENDING_UP if ttype == "Ingreso" else ft.Icons.TRENDING_DOWN
        icon_color = ft.Colors.GREEN_400 if ttype == "Ingreso" else ft.Colors.RED_400
        amount_color = ft.Colors.GREEN_500 if ttype == "Ingreso" else ft.Colors.RED_500
        desc = t.get("description", "N/A")
        date = t.get("date", "N/A")
        cat = t.get("category", "Otros")
        is_dark = self._is_dark()
        return ft.Card(
            content=ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(icon, color=icon_color),
                            padding=10,
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(desc, size=16, weight=ft.FontWeight.BOLD),
                                        self._category_chip(cat),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Text(date, size=12, color=ft.Colors.GREY_600),
                            ],
                            expand=True,
                        ),
                        ft.Text(
                            f"{'+' if ttype == 'Ingreso' else '-'}${abs(amount):.2f}",
                            size=16,
                            color=amount_color,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            tooltip="Editar",
                            on_click=lambda e, tid=t.get("id"): self.page.go(f"/edit_transaction/{tid}") if tid else None,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            tooltip="Eliminar",
                            icon_color=ft.Colors.RED_400,
                            on_click=lambda e, tid=t.get("id"): self.page.run_task(self._delete_transaction(tid)) if tid else None,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=10,
                border_radius=12,
                on_click=lambda e, tid=t.get("id"): self.page.go(f"/edit_transaction/{tid}") if tid else None,
            ),
            elevation=2,
        )

    def _recurring_card(self, r: dict) -> ft.Card:
        amount = float(r.get("amount", 0.0) or 0.0)
        rtype = r.get("type", "Gasto")
        icon = ft.Icons.MONETIZATION_ON if rtype == "Ingreso" else ft.Icons.REPEAT
        icon_color = ft.Colors.GREEN_400 if rtype == "Ingreso" else ft.Colors.BLUE_400
        amount_color = ft.Colors.GREEN_500 if rtype == "Ingreso" else ft.Colors.RED_500
        desc = r.get("description", "Fijo")
        cat = r.get("category", "Otros")
        freq = r.get("frequency", "Mensual")
        chip_freq = ft.Chip(label=ft.Text(freq))
        return ft.Card(
            content=ft.Container(
                content=ft.Row([
                    ft.Container(content=ft.Icon(icon, color=icon_color), padding=10),
                    ft.Column([
                        ft.Row([
                            ft.Text(desc, size=16, weight=ft.FontWeight.BOLD),
                            self._category_chip(cat),
                            chip_freq,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ], expand=True),
                    ft.Text(f"{'+' if rtype == 'Ingreso' else '-'}${abs(amount):.2f}", size=16, color=amount_color),
                    ft.IconButton(icon=ft.Icons.EDIT, tooltip="Editar", on_click=lambda e, rid=r.get("id"): self.page.go(f"/edit_transaction/rec:{rid}") if rid else None),
                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="Eliminar", icon_color=ft.Colors.RED_400, on_click=lambda e, rid=r.get("id"): self.page.run_task(self._delete_recurring(rid)) if rid else None),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=10,
                border_radius=12,
                on_click=lambda e, rid=r.get("id"): self.page.go(f"/edit_transaction/rec:{rid}") if rid else None,
            ), elevation=2)

    async def _delete_transaction(self, transaction_id: str | None):
        if not transaction_id:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, delete_transaction, transaction_id)
        self.transactions = [t for t in self.transactions if t.get("id") != transaction_id]
        user_id = self.page.session.get("user_id")
        if user_id:
            await set_cached_transactions(self.page, user_id, self.transactions)
        self.apply_filters()
        if getattr(self, "page", None) and self._mounted:
            self.page.update()

    async def _delete_recurring(self, recurring_id: str | None):
        if not recurring_id:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, delete_recurring, recurring_id)
        self.recurrings = [r for r in self.recurrings if r.get("id") != recurring_id]
        self.apply_filters()
        if getattr(self, "page", None) and self._mounted:
            self.page.update()

    def set_mode(self, mode: str):
        self.view_mode = mode
        self.apply_filters()
        if getattr(self, "page", None) and self._mounted:
            self.page.update()
