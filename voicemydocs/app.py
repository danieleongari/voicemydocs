import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output

# Initialize the app with a Bootstrap theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Define pages layouts
page0 = html.Div([
    html.H1("Welcome to the Dash App")
])

page1 = html.Div([
    html.H1("Page 1 Title")
])

page2 = html.Div([
    html.H1("Page 2 Title")
])

page3 = html.Div([
    html.H1("Page 3 Title")
])

page4 = html.Div([
    html.H1("Page 4 Title")
])

# Sidebar layout
sidebar = dbc.Col(
    [
        # Top half: Page selection
        dbc.Nav(
            [
                dbc.NavLink("HOME", href="/", id="home-link"),
                dbc.NavLink("STEP 1 | Upload document", href="/page-1", id="page-1-link"),
                dbc.NavLink("STEP 2 | Summarize", href="/page-2", id="page-2-link"),
                dbc.NavLink("STEP 3 | Set the style", href="/page-3", id="page-3-link"),
                dbc.NavLink("STEP 4 | Convert to Audio", href="/page-4", id="page-4-link"),
            ],
            vertical=True,
            pills=True,
        ),
        html.Hr(),
        # Bottom half: Previous projects
        html.Div(
            [
                html.H5("Previous Projects"),
                dcc.Dropdown(
                    id='previous-projects-dropdown',
                    options=[
                        {'label': 'Project 1', 'value': 'proj1'},
                        {'label': 'Project 2', 'value': 'proj2'},
                        {'label': 'Project 3', 'value': 'proj3'},
                    ],
                    placeholder="Load a project"
                )
            ],
            style={'marginTop': '20px'}
        )
    ],
    width=3,
    style={'position': 'fixed', 'height': '100%', 'padding': '20px'}
)

# Main content layout
content = dbc.Col(
    html.Div(id='page-content'),
    width=9,
    style={'marginLeft': '300px', 'padding': '20px'}
)

# App layout
app.layout = dbc.Container(
    [
        dcc.Location(id='url'),
        sidebar,
        content
    ],
    fluid=True
)

# Callback to update the main content based on URL
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    link2page = {
        '/': page0,
        '/page-1': page1,
        '/page-2': page2,
        '/page-3': page3,
        '/page-4': page4
    }
    return link2page.get(pathname, page0)

# Callback to handle loading previous projects
@app.callback(
    Output('page-content', 'children', allow_duplicate=True),
    Input('previous-projects-dropdown', 'value'),
    prevent_initial_call=True
)
def load_project(value):
    if value == 'proj1':
        return page1
    elif value == 'proj2':
        return page2
    elif value == 'proj3':
        return page3
    return dash.no_update

if __name__ == '__main__':
    app.run_server(debug=True)