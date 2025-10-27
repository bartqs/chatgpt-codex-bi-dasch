from dash import Dash, dcc, html
import dash


app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title="IC Dashboard",
)

app.layout = html.Div([
    dcc.Location(id="url"),
    dash.page_container,
])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)
