import importlib.resources as resources

OMIT_FILE = 'ocromit.txt'
H_STROKES_FILE = 'ocromit.txt'
V_STROKES_FILE = 'ocromit.txt'

_ocr_omit = None
_ocr_h_strokes = None
_ocr_v_strokes = None

def ocr_omit():
	if _ocr_omit is None:
		cache_ocr_omit()
	return _ocr_omit

def ocr_h_strokes():
	if _ocr_h_strokes is None:
		cache_ocr_strokes()
	return _ocr_h_strokes

def ocr_v_strokes():
	if _ocr_v_strokes is None:
		cache_ocr_strokes()
	return _ocr_v_strokes

def cache_ocr_omit():
	global _ocr_omit
	_ocr_omit = set()
	with resources.files('hieropy.resources').joinpath(OMIT_FILE).open('r') as f:
		_ocr_omit = set(chr(int(line.split()[0],16)) for line in f)

def cache_ocr_h_strokes():
	global _ocr_h_strokes, _ocr_v_strokes
	_ocr_h_strokes = set()
	_ocr_v_strokes = set()
	with resources.files('hieropy.resources').joinpath(H_STROKES_FILE).open('r') as f:
		_ocr_h_strokes = set(chr(int(line.split()[0],16)) for line in f)
	with resources.files('hieropy.resources').joinpath(V_STROKES_FILE).open('r') as f:
		_ocr_v_strokes = set(chr(int(line.split()[0],16)) for line in f)
