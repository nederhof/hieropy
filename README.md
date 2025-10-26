# hieropy

Python package to manipulate encodings of ancient Egyptian hieroglyphic text.

## Install

DOES NOT YET WORK
```bash
pip3 install hieropy
```

## Use in Python code

Run editor:
```python
from hieropy import UniEditor

UniEditor()
```

Run editor to change entry in database:
```python
from hieropy import UniEditor

database_entry = chr(0x13000)

def save(new_text):
    global database_entry
    database_entry = new_text

def cancel():
    print('cancelled')

UniEditor(text=database_entry, save=save, cancel=cancel)

print('Database entry is now', *[hex(ord(ch)) for ch in database_entry])
```

Convert encoding into image (raster graphics, or PDF, or SVG)
```python
from hieropy import UniParser, Options

parser = UniParser()

encoding = chr(0x13000) + chr(0x13431) + chr(0x13050)
fragment = parser.parse(encoding)

options1 = Options()
printed1 = fragment.print(options1)
printed1.get_pil().save('testimage1.png')

options2 = Options(direction='hrl', fontsize=30, imagetype='pdf')
printed2 = fragment.print(options2)
printed2.get_pil().save('testimage2a.png')
with open('testimage2b.pdf', 'wb') as f:
    f.write(printed2.get_pdf())

options3 = Options(direction='vrl', transparent=True, imagetype='svg')
printed3 = fragment.print(options3)
with open('testimage3.svg', 'w', encoding='utf-8') as f:
    f.write(printed3.get_svg())
```

## Install from GitHub

Download the files.

The first time, run in this directory:
```bash
python3 -m venv .venv
```

Each time after that:
```bash
source .venv/bin/activate
pip3 install -e .
python3 mycode.py
deactivate
```

## Changelog
**v0.1.0**

First release.
