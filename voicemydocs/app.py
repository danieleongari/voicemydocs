import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output
import base64
import io
from PyPDF2 import PdfReader

################### CONSTANTS & FUNCTIONS #############################################################################

VOICE_OPTIONS = [ # https://platform.openai.com/docs/guides/text-to-speech/quickstart
    dict(value="alloy", label="Alloy - pure neutral"),
    dict(value="echo", label="Echo - emphatic neutral"),
    dict(value="faible", label="Faible - emphatic neutral"),
    dict(value="onyx", label="Onyx - man"),
    dict(value="nova", label="Nova - girl"),
    dict(value="shimmer", label="Shimmer - woman"),
]


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
            dbc.Col([
                html.H5("Text extracted from Step 1"),
                dcc.Textarea(
                    id="textarea-file-edit",
                    style={'width': '100%','height': '600px'},
                    readOnly=False
                ),
            ],
            width=6
            ),
            dbc.Col([
                html.H5("Prompt for summarization"),
                dcc.Textarea(
                    id="textarea-prompt-summary",
                    style={'width': '100%','height': '200px'},
                    readOnly=False
                ),
                html.Div(
                    [
                        html.H5("Model to use"),
                        html.A(
                            "ⓘ",
                            href="https://platform.openai.com/docs/models",
                            target="_blank",
                            style={'marginLeft': '10px'},
                        ),
                        dcc.Dropdown(
                            id='dropdown-model-summary',
                            options=[
                                "gpt-4o-2024-08-06",
                                "gpt-4o-mini"
                            ],
                            value='gpt-4o-2024-08-06',
                            style={'marginLeft': '10px', 'width': '250px'}
                        ),
                    ],
                    style={'display': 'flex', 'alignItems': 'center'}
                ),
                dcc.Textarea(
                    id="textarea-summary",
                    style={'width': '100%','height': '350px'},
                    readOnly=True
                ),
            ])
        ])
], id='page-2', style={'display': 'none'})

page3 = html.Div([
    html.H1("Step 3: Make transcript"),
    dbc.Row([
            dbc.Col([
                html.H5("Summarization from Step 2"),
                dcc.Textarea(
                    id="textarea-summary-edit",
                    style={'width': '100%','height': '600px'},
                    readOnly=False
                ),
            ],
            width=6
            ),
            dbc.Col([
                html.H5("Prompt for transcript"),
                dcc.Textarea(
                    id="textarea-prompt-transcript",
                    style={'width': '100%','height': '200px'},
                    readOnly=False
                ),
                html.Div(
                    [
                        html.H5("Model to use"),
                        html.A(
                            "ⓘ",
                            href="https://platform.openai.com/docs/models",
                            target="_blank",
                            style={'marginLeft': '10px'},
                        ),
                        dcc.Dropdown(
                            id='dropdown-model-transcript',
                            options=[
                                "gpt-4o-2024-08-06",
                                "gpt-4o-mini"
                            ],
                            value='gpt-4o-2024-08-06',
                            style={'marginLeft': '10px', 'width': '250px'}
                        ),
                    ],
                    style={'display': 'flex', 'alignItems': 'center'}
                ),
                dcc.Textarea(
                    id="textarea-styling",
                    style={'width': '100%','height': '350px'},
                    readOnly=True
                ),
            ])
        ])
], id='page-3', style={'display': 'none'})

page4 = html.Div([
    html.H1("Step 4: Convert to Audio"),
    dbc.Row([
            dbc.Col([
                html.H5("Final transcript from Step 3"),
                dcc.Textarea(
                    id="textarea-transcript-edit",
                    style={'width': '100%','height': '600px'},
                    readOnly=False
                ),
            ],
            width=6
            ),
            dbc.Col([
                html.Div(
                    [
                        html.H5("Model to use"),
                        dcc.Dropdown(
                            id='dropdown-model-tts',
                            options=[
                                dict(value="tts-1", label="TTS - $0.15/10k chars"),
                                dict(value="tts-1-hd", label="TTS-HD - $0.30/10k chars"),
                            ],
                            value='tts-1',
                            style={'marginLeft': '10px', 'width': '300px'}
                        ),
                    ],
                    style={'display': 'flex', 'alignItems': 'center'}
                ),
                html.Div(
                    [
                        html.H5("Voice for the speakers"),
                        html.A(
                            "ⓘ",
                            href="https://platform.openai.com/docs/guides/text-to-speech/quickstart",
                            target="_blank",
                            style={'marginLeft': '10px'},
                        ),
                    ],
                    style={'display': 'flex', 'alignItems': 'center', 'marginTop': '20px'}
                ),
                html.Div([
                        html.P("Speaker #1", style={'marginLeft': '30px'}),
                        dcc.Dropdown(
                            id='dropdown-speaker1',
                            options=VOICE_OPTIONS,
                            value='nova',
                            style={'marginLeft': '10px', 'width': '300px'}
                        ),
                    ],
                    style={'display': 'flex', 'alignItems': 'center'}
                ),
                html.Div([
                        html.P("Speaker #2", style={'marginLeft': '30px'}),
                        dcc.Dropdown(
                            id='dropdown-speaker2',
                            options=VOICE_OPTIONS,
                            value='echo',
                            style={'marginLeft': '10px', 'width': '300px'}
                        ),
                    ],
                    style={'display': 'flex', 'alignItems': 'center'}
                ),
                html.Div([
                        html.P("Speaker #3", style={'marginLeft': '30px'}),
                        dcc.Dropdown(
                            id='dropdown-speaker3',
                            options=VOICE_OPTIONS,
                            value='onyx',
                            style={'marginLeft': '10px', 'width': '300px'}
                        ),
                    ],
                    style={'display': 'flex', 'alignItems': 'center'}
                ),
                dbc.Button("Convert to Audio", color="primary", className="mr-1", id="button-tts", style={'marginTop': '20px'}),
                dbc.Button("PLACEHOLDER play and download MP3", color="primary", className="mr-1", id="button-tts-placeholder", style={'marginTop': '20px'}),
            ])
        ])    
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
                    dbc.NavLink("STEP 3: Make transcript", href="/page-3", id="page-3-link"),
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
    Output('textarea-file-edit', 'value'),
    Input('upload-pdf', 'contents'),
)
def display_pdf(contents):
    if contents is not None:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        pdf_text = extract_text_from_pdf(decoded)
        
        return contents, pdf_text, pdf_text
    return dash.no_update


if __name__ == '__main__':
    app.run_server(debug=True)