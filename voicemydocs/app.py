import os
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, State, Output
import base64
import io
from PyPDF2 import PdfReader
from dotenv import load_dotenv

from openai import OpenAI

# Search for a .env file in the current directory and load api key
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

################### CONSTANTS & FUNCTIONS #############################################################################

DEFAULT_SUMMARY_PROMPT = """
A text extraction from a PDF document is provided. It could be highly unstructured.
You make a summary of the text highlighting the main points.

You just output the summary, without replying to the user.

You use about 40000 words.
""".strip()

DEFAULT_TRANSCRIPT_PROMPT = """
A summary of an interesting document is provided. 
You make the transcript of a conversation between two speakers discussing the main points of the document.

You don't reply to the user, but you just output the conversation between the two speakers using the following format:
<speaker1>
text
<speaker2>
text
<speaker1>
text
...

You use about 20000 words.

""".strip()

MODEL_DEFAULT = "gpt-4o-mini"

MODEL_OPTIONS = ["gpt-4o-2024-08-06", "gpt-4o-mini"]

VOICE_OPTIONS = [  # https://platform.openai.com/docs/guides/text-to-speech/quickstart
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


def call_llm_api(system_content, user_content, model, api_key):
    client = OpenAI(api_key=OPENAI_API_KEY)

    completion = client.chat.completions.create(
        model=model,
        temperature=1.0,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
    )

    output_content = completion.choices[0].message.content

    return output_content


################### PAGES ###############################################################################################

page0 = html.Div(
    [
        html.H1("Welcome to VoiceMyDocs"),
        html.P("Folow the steps to convert a document into an audio file."),
        html.A(
            "Find here the documentation",
            href="https://docs.google.com/document/d/11uGi8-3JCu3PSPJdwiG-azg6tphVLogrNuRPy4coHo4/edit?usp=sharing",
            target="_blank",
        ),
    ],
    id="page-0",
    style={"display": "none"},
)

page1 = html.Div(
    [
        html.H1("Step 1: Upload document"),
        dcc.Upload(
            id="upload-pdf",
            children=html.Div(["Drag and Drop or ", html.A("Select a PDF File")]),
            style={
                "width": "100%",
                "height": "60px",
                "lineHeight": "60px",
                "borderWidth": "1px",
                "borderStyle": "dashed",
                "borderRadius": "5px",
                "textAlign": "center",
            },
            multiple=False,
        ),
        dbc.Row(
            [
                dbc.Col(
                    html.Iframe(
                        id="iframe-file", style={"width": "100%", "height": "600px"}
                    ),
                    width=6,
                ),
                dbc.Col(
                    dcc.Textarea(
                        id="textarea-file",
                        style={"width": "100%", "height": "600px"},
                        readOnly=True,
                    ),
                    width=6,
                ),
            ]
        ),
    ],
    id="page-1",
    style={"display": "none"},
)

page2 = html.Div(
    [
        html.H1("Step 2: Summarize"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H5("Text extracted from Step 1"),
                        dcc.Textarea(
                            id="textarea-file-edit",
                            style={"width": "100%", "height": "600px"},
                            readOnly=False,
                        ),
                    ],
                    width=6,
                ),
                dbc.Col(
                    [
                        html.H5("Prompt for summarization"),
                        dcc.Textarea(
                            id="textarea-prompt-summary",
                            value=DEFAULT_SUMMARY_PROMPT,
                            style={"width": "100%", "height": "200px"},
                            readOnly=False,
                        ),
                        html.Div(
                            [
                                html.H5("Model to use"),
                                html.A(
                                    "ⓘ",
                                    href="https://platform.openai.com/docs/models",
                                    target="_blank",
                                    style={"marginLeft": "10px"},
                                ),
                                dcc.Dropdown(
                                    id="dropdown-model-summary",
                                    options=MODEL_OPTIONS,
                                    value=MODEL_DEFAULT,
                                    style={"marginLeft": "10px", "width": "250px"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        dbc.Button(
                            "Generate Transcript",
                            color="primary",
                            className="mr-1",
                            id="button-generate-summary",
                            style={"marginTop": "10px"},
                        ),
                        dcc.Loading(
                            id="loading-summary",
                            type="circle",
                            children=dcc.Textarea(
                                id="textarea-summary",
                                style={"width": "100%", "height": "300px"},
                                readOnly=True,
                            ),
                        ),
                    ]
                ),
            ]
        ),
    ],
    id="page-2",
    style={"display": "none"},
)

page3 = html.Div(
    [
        html.H1("Step 3: Make transcript"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H5("Summarization from Step 2"),
                        dcc.Textarea(
                            id="textarea-summary-edit",
                            style={"width": "100%", "height": "600px"},
                            readOnly=False,
                        ),
                    ],
                    width=6,
                ),
                dbc.Col(
                    [
                        html.H5("Prompt for transcript"),
                        dcc.Textarea(
                            id="textarea-prompt-transcript",
                            value=DEFAULT_TRANSCRIPT_PROMPT,
                            style={"width": "100%", "height": "200px"},
                            readOnly=False,
                        ),
                        html.Div(
                            [
                                html.H5("Model to use"),
                                html.A(
                                    "ⓘ",
                                    href="https://platform.openai.com/docs/models",
                                    target="_blank",
                                    style={"marginLeft": "10px"},
                                ),
                                dcc.Dropdown(
                                    id="dropdown-model-transcript",
                                    options=MODEL_OPTIONS,
                                    value=MODEL_DEFAULT,
                                    style={"marginLeft": "10px", "width": "250px"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        dbc.Button(
                            "Generate Transcript",
                            color="primary",
                            className="mr-1",
                            id="button-generate-transcript",
                            style={"marginTop": "10px"},
                        ),
                        dcc.Loading(
                            id="loading-transcript",
                            type="circle",
                            children=dcc.Textarea(
                                id="textarea-transcript",
                                style={"width": "100%", "height": "300px"},
                                readOnly=True,
                            ),
                        ),
                    ]
                ),
            ]
        ),
    ],
    id="page-3",
    style={"display": "none"},
)

page4 = html.Div(
    [
        html.H1("Step 4: Convert to Audio"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H5("Transcript from Step 3"),
                        dcc.Textarea(
                            id="textarea-transcript-edit",
                            style={"width": "100%", "height": "600px"},
                            readOnly=False,
                        ),
                    ],
                    width=6,
                ),
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.H5("Model to use"),
                                dcc.Dropdown(
                                    id="dropdown-model-tts",
                                    options=[
                                        dict(
                                            value="tts-1", label="TTS - $0.15/10k chars"
                                        ),
                                        dict(
                                            value="tts-1-hd",
                                            label="TTS-HD - $0.30/10k chars",
                                        ),
                                    ],
                                    value="tts-1",
                                    style={"marginLeft": "10px", "width": "300px"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        html.Div(
                            [
                                html.H5("Voice for the speakers"),
                                html.A(
                                    "ⓘ",
                                    href="https://platform.openai.com/docs/guides/text-to-speech/quickstart",
                                    target="_blank",
                                    style={"marginLeft": "10px"},
                                ),
                            ],
                            style={
                                "display": "flex",
                                "alignItems": "center",
                                "marginTop": "20px",
                            },
                        ),
                        html.Div(
                            [
                                html.P("Speaker #1", style={"marginLeft": "30px"}),
                                dcc.Dropdown(
                                    id="dropdown-speaker1",
                                    options=VOICE_OPTIONS,
                                    value="nova",
                                    style={"marginLeft": "10px", "width": "300px"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        html.Div(
                            [
                                html.P("Speaker #2", style={"marginLeft": "30px"}),
                                dcc.Dropdown(
                                    id="dropdown-speaker2",
                                    options=VOICE_OPTIONS,
                                    value="echo",
                                    style={"marginLeft": "10px", "width": "300px"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        html.Div(
                            [
                                html.P("Speaker #3", style={"marginLeft": "30px"}),
                                dcc.Dropdown(
                                    id="dropdown-speaker3",
                                    options=VOICE_OPTIONS,
                                    value="onyx",
                                    style={"marginLeft": "10px", "width": "300px"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        dbc.Button(
                            "Convert to Audio",
                            color="primary",
                            className="mr-1",
                            id="button-tts",
                            style={"marginTop": "20px"},
                        ),
                        dbc.Button(
                            "PLACEHOLDER play and download MP3",
                            color="primary",
                            className="mr-1",
                            id="button-tts-placeholder",
                            style={"marginTop": "20px"},
                        ),
                    ]
                ),
            ]
        ),
    ],
    id="page-4",
    style={"display": "none"},
)

################### LAYOUT #############################################################################################

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])


def serve_layout():
    sidebar = dbc.Col(
        [
            dbc.Nav(
                [
                    dbc.NavLink("HOME", href="/", id="home-link"),
                    dbc.NavLink(
                        "STEP 1: Upload document", href="/page-1", id="page-1-link"
                    ),
                    dbc.NavLink("STEP 2: Summarize", href="/page-2", id="page-2-link"),
                    dbc.NavLink(
                        "STEP 3: Make transcript", href="/page-3", id="page-3-link"
                    ),
                    dbc.NavLink(
                        "STEP 4: Convert to Audio", href="/page-4", id="page-4-link"
                    ),
                ],
                vertical=True,
                pills=True,
            ),
            html.Hr(),
            html.H5("OpenAI API Key"),
            dbc.Input(
                id="input-openai-api-key",
                value=OPENAI_API_KEY,
                placeholder="Enter API key...",
                type="password",
                style={"width": "250px"},
            ),
            html.Hr(),
            html.Div(
                [
                    html.H5("Previous Projects"),
                    dcc.Dropdown(
                        id="previous-projects-dropdown",
                        options=[
                            {"label": "Project 1", "value": "proj1"},
                            {"label": "Project 2", "value": "proj2"},
                            {"label": "Project 3", "value": "proj3"},
                        ],
                        placeholder="Load a project",
                    ),
                ],
                style={"marginTop": "20px"},
            ),
        ],
        width=3,
        style={
            "position": "fixed",
            "height": "100%",
            "padding": "20px",
            "width": "300px",
        },
    )

    # Main content layout with all pages
    content = dbc.Col(
        html.Div([page0, page1, page2, page3, page4]),
        width=9,
        style={"marginLeft": "300px", "padding": "20px"},
    )

    return dbc.Container([dcc.Location(id="url"), sidebar, content], fluid=True)


app.layout = serve_layout


################### CALLBACKS ##########################################################################################
@app.callback(
    [
        Output("page-0", "style"),
        Output("page-1", "style"),
        Output("page-2", "style"),
        Output("page-3", "style"),
        Output("page-4", "style"),
    ],
    Input("url", "pathname"),
)
def display_page(pathname):
    styles = [{"display": "none"}] * 5
    if pathname == "/":
        styles[0] = {"display": "block"}
    elif pathname == "/page-1":
        styles[1] = {"display": "block"}
    elif pathname == "/page-2":
        styles[2] = {"display": "block"}
    elif pathname == "/page-3":
        styles[3] = {"display": "block"}
    elif pathname == "/page-4":
        styles[4] = {"display": "block"}
    return styles


@app.callback(
    Output("iframe-file", "src"),
    Output("textarea-file", "value"),
    Output("textarea-file-edit", "value"),
    Input("upload-pdf", "contents"),
)
def display_pdf(contents):
    if contents is not None:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        pdf_text = extract_text_from_pdf(decoded)

        return contents, pdf_text, pdf_text
    return dash.no_update


@app.callback(
    Output("textarea-summary", "value"),
    Output("textarea-summary-edit", "value"),
    Input("button-generate-summary", "n_clicks"),
    State("textarea-file-edit", "value"),
    State("textarea-prompt-summary", "value"),
    State("dropdown-model-summary", "value"),
    State("input-openai-api-key", "value"),
    prevent_initial_call=True,
)
def generate_summary(n_clicks, input_text, prompt, model, api_key):
    if api_key is None:
        return "Please enter your OpenAI API Key..."
    if input_text is None:
        return "Please upload a document first..."

    summary_text = call_llm_api(
        system_content=input_text, user_content=prompt, model=model, api_key=api_key
    )

    return summary_text, summary_text


@app.callback(
    Output("textarea-transcript", "value"),
    Output("textarea-transcript-edit", "value"),
    Input("button-generate-transcript", "n_clicks"),
    State("textarea-summary-edit", "value"),
    State("textarea-prompt-transcript", "value"),
    State("dropdown-model-transcript", "value"),
    State("input-openai-api-key", "value"),
    prevent_initial_call=True,
)
def generate_transcript(n_clicks, input_text, prompt, model, api_key):
    if api_key is None:
        return "Please enter your OpenAI API Key..."
    if input_text is None:
        return "Please upload a document first..."

    transcript_text = call_llm_api(
        system_content=input_text, user_content=prompt, model=model, api_key=api_key
    )

    return transcript_text, transcript_text


if __name__ == "__main__":
    app.run_server(debug=True)
