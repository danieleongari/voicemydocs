# VoiceMyDocs

Convert PDF files to engeging audios, with full control over the whole process.

## Insallation & Usage

```bash
git clone https://github.com/danieleongari/voicemydocs
cd voicemydocs
pip install -e .

python voicemydocs/app.py
```

To avoid inserting the OpenAI API key every time, you can create a `.env` file in the root directory with the following content:

```bash
OPENAI_API_KEY=your_openai_api_key
```

## Development

Quick issues are noted in [this GDoc](https://docs.google.com/document/d/11uGi8-3JCu3PSPJdwiG-azg6tphVLogrNuRPy4coHo4).

Ruff linting and formatting.

```bash
pip install -e.[dev]
pre-commit install
```