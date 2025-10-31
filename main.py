import os
import flet as ft
from views.login_view import LoginView
from views.signup_view import SignupView
from views.dashboard_view import DashboardView
from views.add_transaction_view import AddTransactionView
from views.edit_transaction_view import EditTransactionView
from views.reports_view import ReportsView


def main(page: ft.Page):
    page.title = "App Finanzas"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    def route_change(route):
        page.views.clear()
        if page.route == "/login":
            page.views.append(LoginView(page))
        elif page.route == "/signup":
            page.views.append(SignupView(page))
        elif page.route == "/dashboard":
            page.views.append(DashboardView(page))
        elif page.route == "/add_transaction":
            page.views.append(AddTransactionView(page))
        elif page.route == "/reports":
            page.views.append(ReportsView(page))
        elif page.route.startswith("/edit_transaction/"):
            page.views.append(EditTransactionView(page))

        if page.session.get("authenticated") and page.route in ["/dashboard", "/add_transaction", "/reports"]:
            page.views[0].controls.append(
                ft.NavigationBar(
                    selected_index=0 if page.route == "/dashboard" else (1 if page.route == "/add_transaction" else 2),
                    destinations=[
                        ft.NavigationBarDestination(icon=ft.Icons.DASHBOARD, label="Dashboard"),
                        ft.NavigationBarDestination(icon=ft.Icons.ADD_CARD, label="Add Transaction"),
                        ft.NavigationBarDestination(icon=ft.Icons.PIE_CHART, label="Reports"),
                    ],
                    on_change=lambda e: page.go(
                        "/dashboard" if e.control.selected_index == 0 else (
                            "/add_transaction" if e.control.selected_index == 1 else "/reports"
                        )
                    )
                )
            )
        page.update()

    page.on_route_change = route_change

    async def initialize_app():
        is_logged_in = await page.client_storage.get_async("is_logged_in")
        user_id = await page.client_storage.get_async("user_id")
        if is_logged_in and user_id:
            page.session.set("authenticated", True)
            page.session.set("user_id", user_id)
            page.go("/dashboard")
        else:
            page.go("/login")

    page.run_task(initialize_app)

ft.app(
    target=main,
    view=ft.AppView.WEB_BROWSER,
    port=int(os.environ.get("PORT", 8000))
)
