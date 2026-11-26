# Test fixtures

Saved copies of real pages and robots.txt files. Unit tests read these files instead of
calling live sites, so tests are fast, repeatable and never send traffic to the sites.

All files were saved on **2026-11-26** with the crawler's User-Agent
(`DocsCrawler/0.1 (+https://github.com/RaefKrayem/docs-crawler; mailto:<contact>)`).

## HTML pages

| File | Source URL | How it was saved |
|---|---|---|
| `html/mdn/array-map.html` | https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/map | `curl` |
| `html/mdn/input-element.html` | https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input | `curl` |
| `html/python_docs/stdtypes.html` | https://docs.python.org/3/builtins/stdtypes.html | `curl` (the old `library/stdtypes.html` URL redirects here) |
| `html/python_docs/json.html` | https://docs.python.org/3/library/json.html | `curl` |
| `html/python_docs/asyncio-task.html` | https://docs.python.org/3/library/asyncio-task.html | `curl` |
| `html/devdocs/python-json.html` | https://devdocs.io/python~3.15/library/json | Chrome DevTools, *Copy outerHTML* after the page rendered |
| `html/devdocs/js-array-map.html` | https://devdocs.io/javascript/global_objects/array/map | Chrome DevTools, *Copy outerHTML* after the page rendered |

DevDocs builds its pages with JavaScript, so `curl` only returns an empty shell. The DevDocs
files are the HTML after rendering and have no `<!DOCTYPE>` line.

## robots.txt files

| File | Source URL |
|---|---|
| `robots/mdn.txt` | https://developer.mozilla.org/robots.txt |
| `robots/python_docs.txt` | https://docs.python.org/robots.txt |
| `robots/devdocs.txt` | https://devdocs.io/robots.txt |

## Licences

These copies are kept in a public repository only as test data. The content belongs to its
authors and stays under its original licence:

| Content | Licence (as stated on the saved pages) |
|---|---|
| MDN pages (`html/mdn/`, `html/devdocs/js-array-map.html`) | © 1998–2026 by individual mozilla.org contributors, Creative Commons Attribution-ShareAlike v2.5 or later |
| Python docs pages (`html/python_docs/`, `html/devdocs/python-json.html`) | © 2001 Python Software Foundation, PSF License Version 2; code examples also under the Zero Clause BSD License |
| DevDocs pages | DevDocs republishes the projects' own documentation; each page names its source in a `div._attribution` element |

## Rules

- **Do not edit or reformat these files.** They must stay exact copies of what the sites
  served. Opening and saving them in an editor with format-on-save changes them (in VS Code
  use *Save without Formatting*: `Ctrl+K`, then `S`).
- **To refresh a file**, download it again the same way, update the date above, and re-run
  `uv run pytest`. Expected values in the tests may need to change with the new content.
