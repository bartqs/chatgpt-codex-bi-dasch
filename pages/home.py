import dash
from dash import dcc, html

from data.app_data import IC_BG, IC_GRAY, IC_NAVY, IC_WHITE


dash.register_page(
    __name__,
    path="/",
    name="Pagrindinis",
    title="IC Dashboard",
)


def layout():
    """Minimal landing page linking to the overview and advisor pages."""
    card_style = {
        "border": f"1px solid {IC_GRAY}",
        "borderRadius": "10px",
        "padding": "16px",
        "background": IC_WHITE,
        "width": "280px",
        "textAlign": "center",
        "boxShadow": "0 2px 6px rgba(0,0,0,0.05)",
    }

    link_style = {
        "display": "inline-block",
        "padding": "10px 18px",
        "borderRadius": "6px",
        "background": IC_NAVY,
        "color": IC_WHITE,
        "fontWeight": 600,
        "textDecoration": "none",
        "marginTop": "12px",
    }

    return html.Div(
        [
            html.Div(
                "Inter Cars – BI Dashboard",
                style={"fontSize": "24px", "fontWeight": 800, "color": IC_NAVY, "marginBottom": "20px"},
            ),
            html.Div(
                "Pasirinkite puslapį:",
                style={"fontSize": "16px", "color": IC_NAVY, "marginBottom": "16px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Suvestinė", style={"fontSize": "18px", "fontWeight": 700, "color": IC_NAVY}),
                            html.Div(
                                "Peržiūrėkite filialų rezultatus ir KPI.",
                                style={"marginTop": "8px", "color": "#444"},
                            ),
                            dcc.Link("Atidaryti", href="/overview", style=link_style),
                        ],
                        style=card_style,
                    ),
                    html.Div(
                        [
                            html.Div(
                                "Pardavėjų patarėjas",
                                style={"fontSize": "18px", "fontWeight": 700, "color": IC_NAVY},
                            ),
                            html.Div(
                                "Analizuokite pardavėjų rezultatus ir dinamiką.",
                                style={"marginTop": "8px", "color": "#444"},
                            ),
                            dcc.Link("Atidaryti", href="/sales-advisor", style=link_style),
                        ],
                        style=card_style,
                    ),
                    html.Div(
                        [
                            html.Div(
                                "Klientų apžvalga",
                                style={"fontSize": "18px", "fontWeight": 700, "color": IC_NAVY},
                            ),
                            html.Div(
                                "Segmentų rezultatai ir mėnesinė dinamika.",
                                style={"marginTop": "8px", "color": "#444"},
                            ),
                            dcc.Link("Atidaryti", href="/customers", style=link_style),
                        ],
                        style=card_style,
                    ),
                    html.Div(
                        [
                            html.Div(
                                "Produktų analizė",
                                style={"fontSize": "18px", "fontWeight": 700, "color": IC_NAVY},
                            ),
                            html.Div(
                                "Gamintojų rezultatai pagal metus ir filialus.",
                                style={"marginTop": "8px", "color": "#444"},
                            ),
                            dcc.Link("Atidaryti", href="/product", style=link_style),
                        ],
                        style=card_style,
                    ),
                ],
                style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "justifyContent": "center"},
            ),
        ],
        style={
            "minHeight": "100vh",
            "background": IC_BG,
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "padding": "40px 20px",
        },
    )
