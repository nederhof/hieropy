# hieropy

Python package to manipulate encodings of ancient Egyptian hieroglyphic text.

## Install

```bash
pip install hieropy
```

## Editing

Run Unicode editor:
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

## Rendering

Convert encoding to image (raster graphics or PDF or SVG):
```python
from hieropy import UniParser, Options

parser = UniParser()
encoding = chr(0x13000) + chr(0x13431) + chr(0x13050)
fragment = parser.parse(encoding)
print(parser.last_error) # error message (empty string if no syntax errors in last parse)

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

Options for rendering:

| Name | Default | Values | Purpose |
| ---- | ------- | ------ | ------- |
| direction | 'hlr' | 'hlr', 'hrl', 'vlr', 'vrl' | text direction |
| fontsize | 22 | int (pixels) | font size, determining EM |
| linesize | 1.0 | float (EM) | size of line |
| sep | 0.08 | float (EM) | separation between signs (in EM) |
| hmargin | 0.04 | float (EM) | horizontal margin around hieroglyphic |
| vmargin | 0.04 | float (EM) | vertical margin around hieroglyphic |
| imagetype | 'pil' | 'pil', 'pdf', 'svg' | type of image to be created |
| transparent | False | bool | transparent background |
| signcolor | 'black' | str | name of color for signs |
| bracketcolor | 'red' | str | name of color for brackets |
| shadecolor | 'gray' | str | name of color for shading |
| shadealpha | 128 | int | opacity of shading, between 0 and 255 |
| shadepattern | 'uniform' | 'diagonal', 'uniform' | kind of shading |
| shadedist | 3 | int (pixels) | distance between lines of shading (only for 'diagonal') |
| shadethickness | 1 | int (pixels) | thickness of lines of shading (only for 'diagonal') |
| align | 'middle' | 'middle', 'bottom' | position of signs that are less tall than the line |
| separated | False | bool | hieroglyphic broken up into individual top-level groups |

Some values are expressed as factor of 1 EM (the unscaled height of A1, the "sitting man" sign).

With `imagetype='pdf'`, the created object can be saved as PDF or as raster graphics, as exemplified in the code above. If only raster graphics is needed, then `imagetype='pil'` suffices.

Created SVG files include Unicode characters and still require the NewGardiner font to be displayed. Depending on the platform, there are various tools to turn characters in SVG files into outlines, so that the resulting files can be displayed without needing the font.

With `separated=True`, the `print` method returns a *list* of objects, one for each top-level group in reading order (starting with the rightmost group in the case of `direction='hrl'`). The `separated` option is meant for applications where some other protocol determines line breaks. The images can be concatenated without space in between, and any (diagonal) shading will line up, as if it were one image. The appearance will then be optimal with `imagetype=pil`, while there may be visual artefacts in the case of PDF and SVG.

## Normalization

To normalize hieroglyphic:
```python
from hieropy import UniParser, UniNormalizer

parser = UniParser()
normalizer_legacy = UniNormalizer(types=['legacy'])
normalizer_few = UniNormalizer(types=['aspect','insertion'], excepts=[chr(0x13196)])

encoding = '\U0001310C\U00013196\U00013172\U00013434\U000133CF'
fragment_in = parser.parse(encoding)
fragment_out1 = normalizer_legacy.normalize(fragment_in)
fragment_out2 = normalizer_few.normalize(fragment_in)
print(*[hex(ord(ch)) for ch in str(fragment_out1)])
print(*[hex(ord(ch)) for ch in str(fragment_out2)])
print(normalizer_legacy.errors) # list of strings (error messages for any unimplementable normalizations)
```

Types of normalization:

| Name | Meaning |
| ---- | ------- |
| legacy | do all of: aspect, repetition, transform, variant, overlay, insertion, tabular |
| aspect | replace legacy sign by other that differs only in aspect ratio |
| repetition | replace legacy sign that is repetition of one and the same graphical element |
| transform | replace legacy sign by other with mirroring and/or rotation |
| variant | replace legacy sign by other kind of graphical variant |
| overlay | replace legacy sign by overlay |
| insertion | replace legacy sign by insertion |
| tabular | replace legacy sign by group with horizontal and/or vertical joiners |
| rotation | correct rotation with regard to mirroring |
| order | for overlay of exactly two signs, let first have smaller code point than second |
| damage | remove any damage (i.e. shading) |
| bracket | remove any philological bracket |
| expand | make any lost sign to be expanding |

Legacy characters in the `excepts` list will not be normalized. See further the [list of legacy characters and their types](https://nederhof.github.io/newgardiner/legacy.html).

Normalization with `types=['rotation']` will among other things remove unnecessary mirroring for signs that are symmetric, and may correct rotation for signs for which variation sequences for rotations have been registered. If no appropriate rotation has been registered for a sign, it will leave the existing rotation unaffected however. One can check for unregistered rotations in a fragment by checking whether the `errors` field of an object created with `UniNormalizer(types=['rotation'])`is the empty list after applying its `normalize` method on that fragment.

## Conversion from RES to Unicode

[RES encoding](https://mjn.host.cs.st-andrews.ac.uk/egyptian/res/) of hieroglyphic is more powerful than what Unicode can represent. An instance of the RES-to-Unicode converter collects error messages listing information that may have been lost.

In Unicode, color is not expressed in the encoding itself. When converting from RES, one may either ignore color altogether, or break down a fragment into parts that (predominantly) have the same color, and then implement the colors of these parts in a higher-level protocol.

```python
from hieropy import ResParser, ResUniConverter

parser = ResParser()
res_fragment = parser.parse('A1[red]-B1:Z2[blue]')
converter = ResUniConverter()
uni_fragment = converter.convert_fragment(res_fragment)
print(str(uni_fragment))
for uni_fragment_part in converter.convert_fragment_by_predominant_color(res_fragment):
    print(str(uni_fragment_part), uni_fragment_part.color)
print(converter.errors)
```

## Conversion from Manuel de Codage (MdC) to Unicode

The Manuel de Codage is not so much a single encoding scheme for hieroglyphic text, but rather a family of encoding schemes, implemented by different tools from 1984 onward, many of which added various features, without ever formally documenting their syntax or intended semantics. Moreover, typical MdC implementations allow absolute positioning and scaling, which are beyond the power of Unicode control characters. For these reasons, conversion from arbitrary MdC encodings to Unicode can never be guaranteed to be correctness-preserving. The best one can do is to approximate the intentions of an original encoding, and to report a list of potential problems. In any case, manual checking and correction of output remain necessary.

The conversion implemented here has been tested on a large number of encodings that were created using [JSesh](https://jsesh.qenherkhopeshef.org/), which is the most widely known modern implementation of the MdC, but no doubt one may find other legacy MdC files for which this conversion leaves to be desired.

The input to conversion is a string, possibly containing line breaks:
```python
from hieropy import MdcUniConverter

converter = MdcUniConverter()
uni_fragments = converter.convert('t{{20,655,88}}**w{{278,0,100}}**t{{782,37,76}}\n nfr##v/')
for fragment in uni_fragments:
    print(str(fragment))
print(converter.errors)
```

By default, only a list of hieroglyphic fragments are output and color is ignored, but one may also tell the converter to keep any non-hieroglyphic text (`text=True`) as well as any line numbers (`numbers=True`), and to break fragments where there is a change of (predominant) color between consecutive top-level groups (`colors=True`):
```python
from hieropy import MdcUniConverter
from hieropy.unistructure import Fragment
import hieropy.mdcstructure as mdc

converter = MdcUniConverter(text=True, numbers=True, colors=True)
parts = converter.convert('++JSesh_Info 1.0 +s\n+iTyped by J. Doe+s-!\n|5-A1*B1#23-$r-m!')
for part in parts:
    match part:
        case mdc.LineNumber(): print(f'({part}): ')
        case mdc.Text(): print(f'"{part}"')
        case Fragment(): print(f'[{part.color}] {part}')
```

## OCR/HTR

The implementation of image processing is at a very early stage of development, and would have low accuracy for most practical applications.

The input is assumed to be an image of a single line of hieroglyphic text. The background must be entirely white (not gray) to help segmentation and be free of specks; recognition of shading/hatching and enclosures has not been implemented yet. The tool may also struggle with fonts and handwritings other than the font or handwriting it was created from. There is no language model as yet, which implies that signs that look similar will often be confused.

By default, an instance of the tool is created from the NewGardiner font:
```python
from PIL import Image
from hieropy import UniParser, Options, ImageUniConverter

parser = UniParser()
options = Options(fontsize=30)
encoding_in = '𓂋𓅮𓊛𓐰𓏤𓎔𓐻𓐷𓏏𓐱𓏭𓐸𓁷𓐰𓏤𓈎𓐰𓈖𓈖𓐰𓂡𓀀𓃹𓐰𓈖𓐍𓐰𓂋𓇋𓁷𓐰𓏤𓌞𓋴𓂻'
fragment = parser.parse(encoding_in)
printed = fragment.print(options)
printed.get_pil().save('ocrtest.png')

converter = ImageUniConverter.from_font()
image = Image.open('ocrtest.png')
encoding_out = str(converter.convert_line(image))
print(encoding_in == encoding_out)
```

Another font may be used, and an instance of the tool may be dumped and loaded, to speed up repeated application:
```python
from hieropy import ImageUniConverter

filename = 'pickledconverter.pkl'
converter1 = ImageUniConverter.from_font('OtherFont.ttf')
converter1.dump(filename)
converter2 = ImageUniConverter.load(filename)
```

An instance can also be created from a collection of cropped and labelled exemplars of signs, in a given folder
of PNG images:
```python
from PIL import Image
from hieropy import ImageUniConverter

converter = ImageUniConverter.from_exemplars('sethe')
image = Image.open('htrtest.png')
encoding_out = str(converter.convert_line(image))
```

Here `sethe` would be a folder containing exemplars of Kurt Sethe's handwriting, with filenames like:
```
13000-0-100.png
13000-1-100.png
13014-0-100.png
13014-1-90.png
13191-0-30.png
```

The first number is the code point, the second distinguishes different exemplars of the same sign, and the third is the height of the exemplar relative to the height of the line it was extracted from, as percentage. For example, both exemplars of the sitting man (U+13000) took up 100% of the height of the line, while the viper (U+13191) took up only 30% of that height.

## From GitHub sources

### Install

Download the ZIP file, unpack it and go to the main directory.

### Run in Linux/macOS

One time only, run in this directory:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
deactivate
```

Thereafter, to run Python scripts `mycode1.py` and `mycode2.py`:
```bash
source .venv/bin/activate
python mycode1.py
python mycode2.py
deactivate
```

### Run in Windows CMD

As above, but the first two lines should then be:
```cmd
python -m venv venv
venv\Scripts\activate
```

## Changelog

### 0.1.5

* Added MdC conversion.
* Added OCR/HTR.

### 0.1.4

* Added RES parser and conversion.
* Added normalizations.

### 0.1.3

* Removed need for Poppler to be installed.

### 0.1.2

* First full release.
