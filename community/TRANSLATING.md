# Translating inPace

inPace speaks English and Arabic, and is being translated into more languages. Anything a language
file doesn't have falls back to English, so a half-finished translation is safe to ship.

## How it works

- One file per language: `inpace/locales/<code>.json`, for example `es.json`.
- It's a plain JSON object. The **key is the English text** and the value is your translation:
  ```json
  { "My courses": "Mis cursos" }
  ```
- Add the language to `LANGS` in `inpace/langs.py` (English name, the name in that language,
  `ltr` or `rtl`, and which fonts it needs). Add its short month names to `MONTHS` there too.
- The app restarts to pick up a changed file.

## Rules for a good translation

1. **Never change the key.** It's how inPace finds the text. Copy it exactly, including punctuation
   and the curly quotes (`’`).
2. **Keep every slot exactly as it is**: `{name}`, `{n}`, `{a}`, and `%s`. They get filled in with real
   values. `"%s of %s done"` must still have two `%s`. You may move them if your language needs a
   different word order.
3. **Keep HTML tags** such as `<b>`, `</b>`, `<br>` where they are.
4. **Don't translate names**: inPace, Tempo (the turtle), GitHub, YouTube, Udemy, Git, Markdown, PDF.
5. **Match the tone.** inPace talks like a friendly person, not a manual: short sentences, plain
   everyday words, no jargon. If your language has a formal and an informal "you", use the **informal**
   one (tú, du, tu, 당신 → 너 etc.), because inPace is talking to one learner it knows.
6. **Keep it short.** Buttons and menu items sit in small boxes. If your translation is much longer
   than the English, find a shorter way to say it.
7. **Leave out anything you're unsure of.** A missing line shows the English, which is better than a
   wrong translation.

## Checking your work

```bash
python3 -c "import json,sys; d=json.load(open('inpace/locales/es.json')); print(len(d),'strings')"
python3 -m pytest tests/test_langs.py -q
```

Then open inPace, go to **Settings → Interface language**, pick your language and look around.

## Sending it

Open a pull request, or send the file in the
[Discord](https://mahmoudyosrimahmoud13.github.io/inPace/discord.html) or as a
[GitHub issue](https://github.com/mahmoudyosrimahmoud13/inpace/issues/new?template=feedback.yml).
