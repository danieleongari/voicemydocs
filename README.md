# VoiceMyDocs

Convert PDF files to engaging audios and podcasts, with full control over the whole process.

Find [here](https://open.spotify.com/show/64UjSlOFGykodZwZILqhlX) some examples 
based on [this paper on mine](https://pubs.acs.org/doi/full/10.1021/acsami.9b13357), 
and compared to the two-speakers podcast produced by [NotebookLM](https://notebooklm.google.com/?hl=en).

## Insallation & Usage

```bash
git clone https://github.com/danieleongari/voicemydocs
cd voicemydocs
pip install -e.

python voicemydocs/app.py
```

To avoid inserting the OpenAI API key every time, you can create a `.env` file in the root directory with the following content:

```bash
OPENAI_API_KEY=your_openai_api_key
```

Follow along with the app, it is not supposed to have a documentation.

## Development

Quick issues are noted in [this GDoc](https://docs.google.com/document/d/11uGi8-3JCu3PSPJdwiG-azg6tphVLogrNuRPy4coHo4).

Ruff linting and formatting.

```bash
pip install -e.[dev]
pre-commit install

python voicemydocs/app.py --debug
```

## Acknowledgements

Credit to [PDF2Audio](https://github.com/lamm-mit/PDF2Audio) for inspiration.
