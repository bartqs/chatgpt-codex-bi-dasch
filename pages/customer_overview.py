import dash
from dash import html

from data.app_data import IC_BG, IC_NAVY, IC_WHITE


dash.register_page(
    __name__,
    path="/customers",
    name="Klientų apžvalga",
    title="Klientų apžvalga",
)


def layout():
    """Placeholder layout confirming the customer overview page is active."""
    return html.Div(
        [
            html.Div(
                "Klientų apžvalga – puslapis sukurtas sėkmingai",
                style={
                    "fontSize": "22px",
                    "fontWeight": 700,
                    "color": IC_NAVY,
                    "background": IC_WHITE,
                    "padding": "24px 32px",
                    "borderRadius": "12px",
                    "boxShadow": "0 2px 6px rgba(0, 0, 0, 0.08)",
                },
            )
        ],
        style={
            "minHeight": "100vh",
            "background": IC_BG,
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
        },
    )
