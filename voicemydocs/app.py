import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output
import base64
import io
from PyPDF2 import PdfReader

################### FUNCTIONS ##########################################################################################

def extract_text_from_pdf(pdf_data):
    pdf_reader = PdfReader(io.BytesIO(pdf_data))
    npages = len(pdf_reader.pages)
    text = ""
    for npage, page in enumerate(pdf_reader.pages):
        text += page.extract_text()
        text += f"\n\n>>>>>>>>>>> End Page {npage} of {npages} <<<<<<<<<<<<<\n\n"
    return text

################### PAGES ###############################################################################################

page0 = html.Div([
    html.H1("Welcome to the Dash App")
], id='page-0', style={'display': 'none'})

page1 = html.Div([
    html.H1("Step 1: Upload document"),
    dcc.Upload(
        id='upload-pdf',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select a PDF File')
        ]),
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
        },
        multiple=False
    ),
    dbc.Row([
            dbc.Col(
                html.Iframe(id="iframe-file", style={'width': '100%', 'height': '600px'}),
                width=6
            ),
            dbc.Col(
                dcc.Textarea(
                    id="textarea-file",
                    style={'width': '100%','height': '600px'},
                    readOnly=True
                ),
                width=6
            )
        ])
], id='page-1', style={'display': 'none'})

page2 = html.Div([
    html.H1("Step 2: Summarize"),
    dbc.Row([
            dbc.Col(
                dcc.Textarea(
                    id="textarea-file-edit",
                    style={'width': '100%','height': '600px'},
                    readOnly=True
                ),
                width=6
            )
        ])
    
], id='page-2', style={'display': 'none'})

page3 = html.Div([
    html.H1("Step 3: Set the style")
], id='page-3', style={'display': 'none'})

page4 = html.Div([
    html.H1("Step 4: Convert to Audio")
], id='page-4', style={'display': 'none'})

################### LAYOUT #############################################################################################

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

def serve_layout():
    sidebar = dbc.Col(
        [
            dbc.Nav(
                [
                    dbc.NavLink("HOME", href="/", id="home-link"),
                    dbc.NavLink("STEP 1: Upload document", href="/page-1", id="page-1-link"),
                    dbc.NavLink("STEP 2: Summarize", href="/page-2", id="page-2-link"),
                    dbc.NavLink("STEP 3: Set the style", href="/page-3", id="page-3-link"),
                    dbc.NavLink("STEP 4: Convert to Audio", href="/page-4", id="page-4-link"),
                ],
                vertical=True,
                pills=True,
            ),
            html.Hr(),
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
        style={'position': 'fixed', 'height': '100%', 'padding': '20px', 'width': '300px'}
    )
    
  # Main content layout with all pages
    content = dbc.Col(
        html.Div([
            page0,
            page1,
            page2,
            page3,
            page4
        ]),
        width=9,
        style={'marginLeft': '300px', 'padding': '20px'}
    )
    
    return dbc.Container(
        [
            dcc.Location(id='url'),
            sidebar,
            content
        ],
        fluid=True
    )

app.layout = serve_layout

################### CALLBACKS ##########################################################################################
@app.callback(
    [
        Output('page-0', 'style'),
        Output('page-1', 'style'),
        Output('page-2', 'style'),
        Output('page-3', 'style'),
        Output('page-4', 'style')
    ],
    Input('url', 'pathname')
)
def display_page(pathname):
    styles = [{'display': 'none'}] * 5
    if pathname == '/':
        styles[0] = {'display': 'block'}
    elif pathname == '/page-1':
        styles[1] = {'display': 'block'}
    elif pathname == '/page-2':
        styles[2] = {'display': 'block'}
    elif pathname == '/page-3':
        styles[3] = {'display': 'block'}
    elif pathname == '/page-4':
        styles[4] = {'display': 'block'}
    return styles

@app.callback(
    Output('iframe-file', 'src'),
    Output('textarea-file', 'value'),
    Input('upload-pdf', 'contents'),
)
def display_pdf(contents):
    if contents is not None:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        pdf_text = extract_text_from_pdf(decoded)
        
        return contents, pdf_text
    return dash.no_update


if __name__ == '__main__':
    app.run_server(debug=True)