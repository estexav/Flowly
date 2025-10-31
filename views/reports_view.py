import flet as ft
from services.firebase_service import get_user_transactions
import asyncio
import math

from utils.calculations import calculate_transaction_summary

class ReportsView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.route = "/reports"
        self.transactions = []

        self.appbar = ft.AppBar(
            title=ft.Text("Informes"),
            actions=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    on_click=lambda e: self.page.go("/dashboard"),
                    tooltip="Volver al Dashboard",
                )
            ]
        )

        self.total_income_text = ft.Text("Total Ingresos: $0.00", size=20)
        self.total_expenses_text = ft.Text("Total Gastos: $0.00", size=20)

        self.normal_radius = 100
        self.hover_radius = 110
        self.normal_title_style = ft.TextStyle(
            size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
        )
        self.hover_title_style = ft.TextStyle(
            size=16,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.BOLD,
            shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.BLACK54),
        )

        self.pie_chart = ft.PieChart(
            sections=[],
            sections_space=0,
            center_space_radius=40,
            on_chart_event=self.on_chart_event,
            expand=True,
        )



        self.controls = [
            ft.Column(
                [
                    ft.Text("Resumen de Saldos", size=20, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            self.total_income_text,
                            self.total_expenses_text,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER
                    ),
                    ft.Divider(),
                    ft.Text("Gastos por Categoría", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=self.pie_chart,
                        alignment=ft.alignment.center,
                        padding=ft.padding.only(top=20, bottom=20)
                    ),
                    ft.Divider(),

                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.START,
                expand=True,
                scroll=ft.ScrollMode.ADAPTIVE
            )
        ]

    def did_mount(self):
        self.page.run_task(self.load_reports)

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
        user_id = self.page.session.get("user_id")
        if user_id:
            loop = asyncio.get_event_loop()
            self.transactions = await loop.run_in_executor(None, get_user_transactions, user_id)

            total_income, total_expenses, _ = calculate_transaction_summary(self.transactions)

            self.total_income_text.value = f"Total Ingresos: {total_income:.2f}"
            self.total_expenses_text.value = f"Total Gastos: {total_expenses:.2f}"

            # Actualizar gráfico de pastel
            pie_chart_sections = self._create_pie_chart_data(self.transactions)
            self.pie_chart.sections = pie_chart_sections



            self.page.update()

    def _create_pie_chart_data(self, transactions):
        category_data = {}
        for t in transactions:
            transaction_type = t.get("type")
            category = t.get("category", "Sin Categoría")
            amount = float(t.get("amount", 0))

            if transaction_type == "Gasto":
                key = f"Gasto - {category}"
                category_data[key] = category_data.get(key, 0) + amount
            elif transaction_type == "Ingreso":
                key = f"Ingreso - {category}"
                category_data[key] = category_data.get(key, 0) + amount

        chart_data = []
        # Define a color palette
        colors = [
            ft.Colors.BLUE_ACCENT_700, ft.Colors.GREEN_ACCENT_700, ft.Colors.RED_ACCENT_700,
            ft.Colors.PURPLE_ACCENT_700, ft.Colors.ORANGE_ACCENT_700, ft.Colors.TEAL_ACCENT_700,
            ft.Colors.CYAN_ACCENT_700, ft.Colors.PINK_ACCENT_700, ft.Colors.LIME_ACCENT_700,
            ft.Colors.INDIGO_ACCENT_700, ft.Colors.BROWN_700, ft.Colors.DEEP_ORANGE_700,
            ft.Colors.LIGHT_BLUE_700, ft.Colors.LIGHT_GREEN_700, ft.Colors.AMBER_700
        ]
        color_index = 0
        for category_name, amount in category_data.items():
            chart_data.append(ft.PieChartSection(
                value=amount,
                title=f"{category_name} (${amount:.2f})",
                color=colors[color_index % len(colors)], # Assign color from palette
                radius=self.normal_radius,
                title_style=self.normal_title_style
            ))
            color_index += 1
        return chart_data

