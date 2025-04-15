import os
import argparse
import base64
import io
import json
from datetime import datetime
from PyPDF2 import PdfReader
from openai import OpenAI
from dotenv import load_dotenv
import concurrent.futures as cf

import dash
from dash import html, dcc, Input, State, Output
import dash_bootstrap_components as dbc

from flask import Flask, send_from_directory

# Search for a .env file in the current directory and load api key
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

################### CONSTANTS & FUNCTIONS #############################################################################

CACHE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), ".voicemydocs_cache/"
)
os.makedirs(CACHE_DIRECTORY, exist_ok=True)

DEFAULT_SUMMARY_PROMPT = """
You are given a text extracted from a PDF document, which may be highly unstructured. 
Your task is to rewrite the content in a more structured and coherent form, organizing the information logically and clearly.

In particular, focus on highlighting the following aspects:

- Authorship and Expertise: Identify the authors of the document and provide details about their background and areas of expertise.  
- General Context: Summarize the broader context or motivation of the study.  
- Methodology: Describe the techniques and methodologies used in the study, including technical details, as if you were explaining them to an expert in the field.  
- Results: Present the results obtained in the study, strictly reporting the factual findings without adding interpretation or speculation.  
- Significance: Discuss the relevance and potential impact of the results in a broader scientific or practical context.  
- Limitations and Critical Evaluation: Point out the limitations of the techniques and analyses used, and include any critical or skeptical considerations that are supported by the text.

Your output should be a comprehensive and detailed text that includes all the information contained in the original document. 
Do not omit any data or claims present in the source.  
Return only the rewritten report — do not include any introductory or closing remarks directed at the user.
""".strip()

DEFAULT_TRANSCRIPT_PROMPT = """
You are given a summarization of a document. 
Your task is to produce a transcript of a conversation between two speakers who are discussing the main points of the document.
Both speakers are experts in the field, and they are addressing a general but PhD-level audience. 
The conversation should be intellectually engaging, with the speakers interacting naturally and dynamically. 
They should go through all the information in the document, offering long and detailed discussions.

You must include all the content from the original document in the conversation. 
The style should be conversational yet informative, resembling a high-level academic discussion or podcast.

Format the output as follows:
<speaker1>
text
<speaker2>
text
<speaker1>
text
...

Do not reply to the user—just output the conversation between the two speakers using the format above.
""".strip()

DEBUG_DIALOGUE = """
<Alice>
Hello, how are you?
<Berto>
I'm good, thanks! How about you?
<Alice>
I'm doing great, thanks for asking!
<Berto>
That's good to hear!
<Claudio>
Hey guys, what are you talking about?
""".strip()

MODEL_OPTIONS = [
    "gpt-4.1-nano-2025-04-14",
    "gpt-4.1-mini-2025-04-14",
    "gpt-4.1-2025-04-14",
    "o3-mini-2025-01-31",
    "gpt-4o-2024-11-20",
    "gpt-4o-2024-08-06",
    "gpt-4o-mini",
]

MODEL_DEFAULT = MODEL_OPTIONS[0]

TTS_OPTIONS = [
    {
        "model": "tts-1",
        "label": "TTS",
        "cost": 0.15,  # per 10k chars
    },
    {
        "model": "tts-1-hd",
        "label": "TTS-HD",
        "cost": 0.30,  # per 10k chars
    },
    {
        "model": "gpt-4o-mini-tts",
        "label": "TTS-GPT",
        "cost": 0.12,  # per 10k chars
    },
]

TTS_DEFAULT = TTS_OPTIONS[0]


def get_tts_cost(tts_model, n_chars):
    """Get the cost of the TTS model for the given number of characters."""
    for option in TTS_OPTIONS:
        if option["model"] == tts_model:
            return option["cost"] * n_chars / 10000
    raise ValueError(f"Unknown TTS model: {tts_model}")


VOICE_OPTIONS = [  # https://platform.openai.com/docs/guides/text-to-speech/quickstart
    dict(value="alloy", label="Alloy - pure neutral"),
    dict(value="echo", label="Echo - emphatic neutral"),
    dict(value="fable", label="Fable - emphatic neutral"),
    dict(value="onyx", label="Onyx - man"),
    dict(value="nova", label="Nova - girl"),
    dict(value="shimmer", label="Shimmer - woman"),
]

with open(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "assets/showcase_tts_6voices.mp3"
    ),
    "rb",
) as audio_file:
    DEFAULT_AUDIO_SRC = "data:audio/mp3;base64," + base64.b64encode(
        audio_file.read()
    ).decode("utf-8")


def extract_text_from_pdf(pdf_data):
    pdf_reader = PdfReader(io.BytesIO(pdf_data))
    npages = len(pdf_reader.pages)
    text = ""
    for npage, page in enumerate(pdf_reader.pages):
        text += page.extract_text()
        text += f"\n\n>>>>>>>>>>> End Page {npage} of {npages} <<<<<<<<<<<<<\n\n"
    return text


def call_llm_api(system_content, user_content, model, api_keys):
    """Call the OpenAI API to get the response from the LLM."""

    if not api_keys["openai"]:
        return "Please insert your OpenAI API Key first..."

    client = OpenAI(api_key=api_keys["openai"])

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


def call_tts_api(text: str, voice: str, tts_model: str, api_key: str) -> bytes:
    client = OpenAI(api_key=api_key)

    with client.audio.speech.with_streaming_response.create(
        model=tts_model,
        voice=voice,
        input=text,
    ) as response:
        with io.BytesIO() as file:
            for chunk in response.iter_bytes():
                file.write(chunk)
            return file.getvalue()  # Mp3


def dialogue_text2list(dialogue: str) -> list:
    """Converts a dialogue string into a list of dictionaries, e.g.,
    [ {'speaker': 1, 'text': 'Hello, how are you?'},
    {'speaker': 2, 'text': "I'm good, thanks! How about you?"},
    ...]
    """

    lines = [line.strip() for line in dialogue.strip().split("\n") if line.strip()]
    dialogue_list = []
    speakers = []

    # Iterate through the lines
    for line in lines:
        if line.strip().startswith("<") and line.strip().endswith(">"):
            current_speaker = line.strip()
            if line not in speakers:
                speakers.append(line)
        elif len(speakers) > 0:
            speaker_index = speakers.index(current_speaker) + 1
            dialogue_list.append({"speaker": speaker_index, "text": line})
        else:
            continue

    return dialogue_list


def compile_dialogue(
    dialogue_text,
    speakers_voice=["nova", "echo", "onyx"],
    tts_model=TTS_DEFAULT["model"],
    api_key=None,
):
    """Inspired to PDF2Audio"""

    dialogue_list = dialogue_text2list(dialogue_text)

    audio = b""
    with cf.ThreadPoolExecutor() as executor:
        futures = []
        counter = 0
        for dialogue_dict in dialogue_list:
            counter += 1
            future = executor.submit(
                call_tts_api,
                dialogue_dict["text"],
                speakers_voice[dialogue_dict["speaker"] - 1],
                tts_model,
                api_key,
            )
            futures.append(future)

        for future in futures:
            audio_chunk = future.result()
            audio += audio_chunk

    return audio


################### PAGES ###############################################################################################

page0 = html.Div(
    [
        html.H1("Welcome to VoiceMyDocs"),
        html.P("Folow the steps to convert a document into an audio file."),
        html.A(
            "Find here the README documentation",
            href="https://github.com/danieleongari/voicemydocs",
            target="_blank",
        ),
        html.Div(style={"height": "30px"}),
        html.H5("Insert your API Keys"),
        html.P("OpenAI API Key", style={"marginTop": "10px", "marginBottom": "0px"}),
        dbc.InputGroup(
            [
                dbc.Button(
                    "👁️",
                    id="toggle-password-openai",
                    n_clicks=0,
                    style={"width": "40px"},
                ),
                dbc.Input(
                    id="input-openai-api-key",
                    type="password",
                    placeholder="Enter API key...",
                    value=OPENAI_API_KEY,
                ),
            ]
        ),
        html.P(
            "Anthropic API Key (currently not implemented)",
            style={"marginTop": "10px", "marginBottom": "0px"},
        ),
        dbc.InputGroup(
            [
                dbc.Button(
                    "👁️",
                    id="toggle-password-anthropic",
                    n_clicks=0,
                    style={"width": "40px"},
                ),
                dbc.Input(
                    id="input-anthropic-api-key",
                    value=None,
                    placeholder="Enter API key...",
                    type="password",
                    style={"width": "250px"},
                ),
            ]
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
                        id="iframe-file",
                        src="/assets/pdf-placeholder.svg",
                        style={
                            "width": "100%",
                            "height": "600px",
                            "border": "none",
                        },
                    ),
                    width=6,
                ),
                dbc.Col(
                    dcc.Loading(
                        id="loading-file",
                        type="circle",
                        children=dcc.Textarea(
                            id="textarea-file",
                            style={"width": "100%", "height": "600px"},
                            readOnly=True,
                        ),
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
                                    clearable=False,
                                    style={"marginLeft": "10px", "width": "270px"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        dbc.Button(
                            "Generate Summary",
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
                                    clearable=False,
                                    style={"marginLeft": "10px", "width": "270px"},
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
                            value=None,
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
                                        {
                                            "value": x["model"],
                                            "label": f"{x['label']} = ${x['cost']}/10k chars",
                                        }
                                        for x in TTS_OPTIONS
                                    ],
                                    value=TTS_DEFAULT["model"],
                                    clearable=False,
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
                                    clearable=False,
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
                                    clearable=False,
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
                                    clearable=False,
                                    style={"marginLeft": "10px", "width": "300px"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        dbc.Button(
                            "Convert to Audio & Save the Project",
                            color="primary",
                            className="mr-1",
                            id="button-tts",
                            style={"marginTop": "20px"},
                        ),
                        dcc.Loading(
                            id="loading-audio",
                            type="circle",
                            children=html.Audio(
                                id="audio-player",
                                src=DEFAULT_AUDIO_SRC,
                                controls=True,
                                style={"width": "100%", "height": "50px"},
                            ),
                        ),
                        html.Small(
                            "NOTE: once you generate the audio, all the previous steps will be saved. Each previous project is labelled with the timedate of creation, and can be loaded from the bottom left dropdown."
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

server = Flask(__name__)
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="VoiceMyDocs",
    server=server,
)


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
            html.H5("Project Counters"),
            html.Small(
                id="counter-document",
                children="Document: 0c 0w 0p",
                style={"left": "10px", "position": "relative", "margin": "5px"},
            ),
            html.Br(),
            html.Small(
                id="counter-summary",
                children="Summary: 0c 0w",
                style={"left": "10px", "position": "relative", "margin": "5px"},
            ),
            html.Br(),
            html.Small(
                id="counter-transcript",
                children="Transcription: 0c 0w 0d",
                style={"left": "10px", "position": "relative", "margin": "5px"},
            ),
            html.Br(),
            html.Small(
                id="counter-audio",
                children="Audio: 0:00s $0.00",
                style={"left": "10px", "position": "relative", "margin": "5px"},
            ),
            html.Hr(),
            html.H5("Previous Projects"),
            dcc.Dropdown(
                id="dropdown-previous-projects",
                placeholder="Load a past project...",
                maxHeight=100,
            ),
            html.Small(
                id="previous-projects-info",
                children="You have xx past projects",
                style={"left": "10px", "position": "relative", "margin": "5px"},
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

    return dbc.Container(
        [dcc.Location(id="url"), dcc.Store(id="stored-audio"), sidebar, content],
        fluid=True,
    )


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
    Output("input-openai-api-key", "type"),
    Input("toggle-password-openai", "n_clicks"),
)
def toggle_openai_password_visibility(n_clicks):
    if n_clicks and n_clicks % 2 == 1:
        return "text"
    return "password"


@app.callback(
    Output("input-anthropic-api-key", "type"),
    Input("toggle-password-anthropic", "n_clicks"),
)
def toggle_anthropic_password_visibility(n_clicks):
    if n_clicks and n_clicks % 2 == 1:
        return "text"
    return "password"


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
    return "/assets/pdf-placeholder.svg", None, None


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
def generate_summary(n_clicks, input_text, prompt, model, openai_key):
    if input_text is None:
        return "Please upload a document first..."

    summary_text = call_llm_api(
        system_content=prompt,
        user_content=input_text,
        model=model,
        api_keys={"openai": openai_key},
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
def generate_transcript(n_clicks, input_text, prompt, model, openai_key):
    if input_text is None:
        return "Please upload a document first..."

    transcript_text = call_llm_api(
        system_content=prompt,
        user_content=input_text,
        model=model,
        api_keys={"openai": openai_key},
    )

    return transcript_text, transcript_text


@app.callback(
    Output("stored-audio", "data"),
    Output("audio-player", "src"),
    Input("button-tts", "n_clicks"),
    State("textarea-transcript-edit", "value"),
    State("dropdown-speaker1", "value"),
    State("dropdown-speaker2", "value"),
    State("dropdown-speaker3", "value"),
    State("dropdown-model-tts", "value"),
    State("input-openai-api-key", "value"),
    prevent_initial_call=True,
)
def text2audio_store_play(
    n_clicks, transcript, speaker1, speaker2, speaker3, tts_model, api_key
):
    if api_key is None:
        return "Please enter your OpenAI API Key..."
    if transcript is None:
        return "Please generate a transcript first..."

    speakers_voice = [speaker1, speaker2, speaker3]
    audio_data = compile_dialogue(transcript, speakers_voice, tts_model, api_key)

    audio_data_base64 = base64.b64encode(audio_data).decode("utf-8")

    return audio_data_base64, f"data:audio/mp3;base64,{audio_data_base64}"


@server.route("/.voicemydocs_cache/<path:filename>")
def download_file(filename):
    return send_from_directory(CACHE_DIRECTORY, filename)


def get_log_dict(*args):
    keys = [
        "file-text",
        "summary-prompt",
        "summary-model",
        "summary-text",
        "transcript-prompt",
        "transcript-model",
        "transcript-text",
        "tts-model",
        "speaker1",
        "speaker2",
        "speaker3",
        "counter-document",
        "counter-summary",
        "counter-transcript",
        "counter-audio",
    ]

    args = list(args)
    iarg_file_text = keys.index("transcript-text")
    args[iarg_file_text] = dialogue_text2list(args[iarg_file_text])

    return dict(zip(keys, args))


@app.callback(
    Output("previous-projects-info", "children", allow_duplicate=True),  # dummy
    Input("stored-audio", "data"),
    State("textarea-file-edit", "value"),
    State("textarea-prompt-summary", "value"),
    State("dropdown-model-summary", "value"),
    State("textarea-summary-edit", "value"),
    State("textarea-prompt-transcript", "value"),
    State("dropdown-model-transcript", "value"),
    State("textarea-transcript-edit", "value"),
    State("dropdown-model-tts", "value"),
    State("dropdown-speaker1", "value"),
    State("dropdown-speaker2", "value"),
    State("dropdown-speaker3", "value"),
    State("counter-document", "children"),
    State("counter-summary", "children"),
    State("counter-transcript", "children"),
    State("counter-audio", "children"),
    prevent_initial_call=True,
)
def write_checkpoint(audio_data_base64, *args):
    """When the audio is generated, store the mp3 file and the draft (with all the text, prompt and settings used)
    as CACHE_DIRECTORY/filename.mp3 and .json, respectively.
    These files will be subsequently available as "Previous Projects" to be reloaded and edited.
    """

    if audio_data_base64 is None:
        return dash.no_update

    audio_data = base64.b64decode(audio_data_base64)

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    audio_file_path = os.path.join(CACHE_DIRECTORY, f"{filename}.mp3")

    with open(audio_file_path, "wb") as audio_file:
        audio_file.write(audio_data)

    draft_dict = get_log_dict(*args)
    draft_file_path = os.path.join(CACHE_DIRECTORY, f"{filename}.json")

    with open(draft_file_path, "w") as draft_file:
        json.dump(draft_dict, draft_file, indent=4)

    return "Adding a new project..."


@app.callback(
    Output("dropdown-previous-projects", "options"),
    Output("previous-projects-info", "children"),
    Input("previous-projects-info", "children"),
)
def load_previous_projects(dummy):
    """Load the list of previous projects from the CACHE_DIRECTORY and return the list of filenames."""
    files = os.listdir(CACHE_DIRECTORY)
    filenames_valid = [
        f.split(".")[0]
        for f in files
        if f.endswith(".mp3") and f"{f[:-4]}.json" in files
    ]
    filenames_valid.sort(reverse=True)  # sort from most recent to oldest
    return filenames_valid, f"You have {len(filenames_valid)} past projects"


def transcript_dict2text(transcript_dict):
    """Converts a list of dictionaries into a dialogue string, e.g.,
    ---
    [ {'speaker': 1, 'text': 'Hello, how are you?'},
    {'speaker': 2, 'text': "I'm good, thanks! How about you?"},
    ...]
    ---
    <speaker1>
    Hello, how are you?
    <speaker2>
    I'm good, thanks! How about you?
    """

    lines = []
    for dialogue_dict in transcript_dict:
        lines.append(f"<speaker{dialogue_dict['speaker']}>\n{dialogue_dict['text']}")

    return "\n".join(lines)


@app.callback(
    Output("textarea-file-edit", "value", allow_duplicate=True),
    Output("textarea-prompt-summary", "value", allow_duplicate=True),
    Output("dropdown-model-summary", "value", allow_duplicate=True),
    Output("textarea-summary-edit", "value", allow_duplicate=True),
    Output("textarea-prompt-transcript", "value", allow_duplicate=True),
    Output("dropdown-model-transcript", "value", allow_duplicate=True),
    Output("textarea-transcript-edit", "value", allow_duplicate=True),
    Output("dropdown-model-tts", "value", allow_duplicate=True),
    Output("dropdown-speaker1", "value", allow_duplicate=True),
    Output("dropdown-speaker2", "value", allow_duplicate=True),
    Output("dropdown-speaker3", "value", allow_duplicate=True),
    Output("audio-player", "src", allow_duplicate=True),
    Input("dropdown-previous-projects", "value"),
    prevent_initial_call=True,
)
def load_previous_project(filename):
    """Load the data from the selected project and return the values to the corresponding components.
    Assuming that the order of the output is the same as the order of the json keys,
    excluding the counters that are in the last positions.
    """
    if filename is None:
        return [  # default values
            None,
            DEFAULT_SUMMARY_PROMPT,
            MODEL_DEFAULT,
            None,
            DEFAULT_TRANSCRIPT_PROMPT,
            MODEL_DEFAULT,
            None,
            TTS_DEFAULT["model"],
            "nova",
            "echo",
            "onyx",
            DEFAULT_AUDIO_SRC,
        ]

    draft_file_path = os.path.join(CACHE_DIRECTORY, f"{filename}.json")
    with open(draft_file_path, "r") as draft_file:
        draft_dict = json.load(draft_file)

    draft_dict["transcript-text"] = transcript_dict2text(draft_dict["transcript-text"])

    # load mp3 file
    audio_file_path = os.path.join(CACHE_DIRECTORY, f"{filename}.mp3")
    with open(audio_file_path, "rb") as audio_file:
        audio_data = audio_file.read()
        audio_data_base64 = base64.b64encode(audio_data).decode("utf-8")
        audio_src = f"data:audio/mp3;base64,{audio_data_base64}"

    return list(draft_dict.values())[:11] + [audio_src]


#### COUNTERS CALLBACKS #########################################################


@app.callback(
    Output("counter-document", "children"),
    Input("textarea-file-edit", "value"),
    prevent_initial_call=False,
)
def update_counter_document(text):
    if text is None:
        words = chars = pages = 0
    else:
        chars = len(text)
        words = len(text.split())
        pages = len([x for x in text.strip().split(">>>>>>>>>>> End Page") if x])
    return f"Document: {chars}c {words}w {pages}p"


@app.callback(
    Output("counter-summary", "children"),
    Input("textarea-summary-edit", "value"),
    prevent_initial_call=False,
)
def update_counter_summary(text):
    if text is None:
        words = chars = 0
    else:
        chars = len(text)
        words = len(text.split())
    return f"Summary: {chars}c {words}w"


@app.callback(
    Output("counter-transcript", "children"),
    Output("counter-audio", "children"),
    Input("textarea-transcript-edit", "value"),
    Input("dropdown-model-tts", "value"),
)
def update_counter_transcript(text, tts_model):
    if text is None:
        words = chars = dialogues = estimated_audio_seconds = estimated_price = 0
    else:
        CHARS2SEC = 1 / 20  # This is a rough estimate - TODO: improve
        words = len(text.split())
        chars = len(text)
        dialogues = len([x for x in text.strip().split("<speaker") if x])
        estimated_audio_seconds = int(chars * CHARS2SEC)
        estimated_price = get_tts_cost(tts_model, chars)

    minutes, seconds = divmod(estimated_audio_seconds, 60)

    return [
        f"Transcription: {chars}c {words}w {dialogues}d",
        f"Audio:   {minutes:d}:{seconds:02d}s ${estimated_price:.2f}",
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the VoiceMyDocs app.")
    parser.add_argument(
        "--debug", action="store_true", help="Run the app in debug mode."
    )
    args = parser.parse_args()

    app.run(debug=args.debug)
