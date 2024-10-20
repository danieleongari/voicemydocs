import os
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
print(f"CACHE_DIRECTORY={CACHE_DIRECTORY}")

DEFAULT_SUMMARY_PROMPT = """
A text extraction from a PDF document is provided. It could be highly unstructured.
You rewrite the document in a more structured way, highlighting the main points.
In particular you want to highlight:
* Who are the authors of the document, and what is their expertise
* A general context of the study
* The techniques used, going into the details as you were speaking to an expert in the field
* the results they got, without any speculation: just the facts
* the importance of the results that they got in a broader context 
* the limits of their tecniques and analysis, and some skeptical considerations
Your output is a very long text where all the informations that were present in the original document are present.
You just output the output report, without replying to the user.
""".strip()

DEFAULT_TRANSCRIPT_PROMPT = """
A text summarization of a document is provided.
You make the transcript of a conversation between two speakers discussing the main points of the document.
They are both experts in the field, and they try to address a more general, but phd-level audience.
The two speakers interact with each other, in a very engaging way for the listener.
They go through all the information contained in the document, making long and detailled speeches.

You don't reply to the user, but you just output the conversation between the two speakers using the following format:
<speaker1>
text
<speaker2>
text
<speaker1>
text
...

The conversation is long, and the speaker cover all the information contained in the document.

""".strip()

DEBUG_DIALOGUE = """
<speaker1>
Hello, how are you?
<speaker2>
I'm good, thanks! How about you?
<speaker1>
I'm doing great, thanks for asking!
<speaker2>
That's good to hear!
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
    client = OpenAI(api_key=api_key)

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
    current_speaker = None

    # Iterate through the lines
    for line in lines:
        if line.lower().startswith("<speaker"):
            current_speaker = int(line.lower().strip("<speaker>"))
        else:
            dialogue_list.append({"speaker": current_speaker, "text": line})

    return dialogue_list


def compile_dialogue(
    dialogue_text,
    speakers_voice=["nova", "echo", "onyx"],
    tts_model="tts-1",
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
                            value=DEBUG_DIALOGUE,
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
                        html.Audio(
                            id="audio-player",
                            src="https://www.computerhope.com/jargon/m/example.mp3",
                            controls=True,
                            style={"width": "100%", "height": "50px"},
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
            html.P(
                id="counter-document",
                children="Document: 0c 0w 0p",
                style={"left": "10px", "position": "relative", "margin": "5px"},
            ),
            html.P(
                id="counter-summary",
                children="Summary: 0c 0w",
                style={"left": "10px", "position": "relative", "margin": "5px"},
            ),
            html.P(
                id="counter-transcript",
                children="Transcription: 0c 0w 0d",
                style={"left": "10px", "position": "relative", "margin": "5px"},
            ),
            html.P(
                id="counter-audio",
                children="Audio: 0:00s $0.00",
                style={"left": "10px", "position": "relative", "margin": "5px"},
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


@app.callback(
    Output("stored-audio", "data"),
    Input("button-tts", "n_clicks"),
    State("textarea-transcript-edit", "value"),
    State("dropdown-speaker1", "value"),
    State("dropdown-speaker2", "value"),
    State("dropdown-speaker3", "value"),
    State("dropdown-model-tts", "value"),
    State("input-openai-api-key", "value"),
    prevent_initial_call=True,
)
def convert_to_audio_and_save_files(
    n_clicks, transcript, speaker1, speaker2, speaker3, tts_model, api_key
):
    if api_key is None:
        return "Please enter your OpenAI API Key..."
    if transcript is None:
        return "Please generate a transcript first..."

    speakers_voice = [speaker1, speaker2, speaker3]
    audio_data = compile_dialogue(transcript, speakers_voice, tts_model, api_key)

    audio_data_base64 = base64.b64encode(audio_data).decode("utf-8")

    return audio_data_base64


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
    Output("button-tts", "children"),  # dummy
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
def store_audio_adn_draft(audio_data_base64, *args):
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

    return dash.no_update


@app.callback(
    Output("audio-player", "src"),
    Input("stored-audio", "data"),
    prevent_initial_call=True,
)
def update_audio_player(audio_data_base64):
    if audio_data_base64:
        audio_src = f"data:audio/mp3;base64,{audio_data_base64}"
        return audio_src
    return None


# ### COUNTERS CALLBACKS #########################################################


@app.callback(
    Output("counter-document", "children"),
    Input("textarea-file-edit", "value"),
    prevent_initial_call=False,
)
def update_counter_document(text):
    if text is None:
        words = chars = 0
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
        price_per_10k_char = {"tts-1": 0.15, "tts-1-hd": 0.30}[tts_model]
        estimated_price = chars * price_per_10k_char / 10000

    minutes, seconds = divmod(estimated_audio_seconds, 60)

    return [
        f"Transcription: {chars}c {words}w {dialogues}d",
        f"Audio:   {minutes:d}:{seconds:02d}s ${estimated_price:.2f}",
    ]


if __name__ == "__main__":
    app.run_server(debug=True)
