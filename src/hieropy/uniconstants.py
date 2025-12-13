VER	       = '\U00013430'
HOR	       = '\U00013431'
INSERT_TS  = '\U00013432'
INSERT_BS  = '\U00013433'
INSERT_TE  = '\U00013434'
INSERT_BE  = '\U00013435'
OVERLAY    = '\U00013436'
BEGIN_SEGMENT = '\U00013437'
END_SEGMENT = '\U00013438'
INSERT_M   = '\U00013439'
INSERT_T   = '\U0001343A'
INSERT_B   = '\U0001343B'
MIRROR     = '\U00013440'
FULL_BLANK = '\U00013441'
HALF_BLANK = '\U00013442'
FULL_LOST  = '\U00013443'
HALF_LOST  = '\U00013444'
TALL_LOST  = '\U00013445'
WIDE_LOST  = '\U00013446'

BEGIN_ENCLOSURE        = '\U0001343C'
END_ENCLOSURE          = '\U0001343D'
BEGIN_WALLED_ENCLOSURE = '\U0001343E'
END_WALLED_ENCLOSURE   = '\U0001343F'
OPEN_BOX               = '\U00013379'
CLOSE_BOX              = '\U0001337A'
OPEN_WALLED            = '\U00013286'
CLOSE_WALLED           = '\U00013287'

OPENING_PLAIN_CHARS = '\U00013258\U00013259\U0001325A\U00013379\U0001342F'
OPENING_WALLED_CHARS = '\U00013286\U00013288'
OPENING_CHARS = OPENING_PLAIN_CHARS + OPENING_WALLED_CHARS
CLOSING_PLAIN_CHARS = '\U0001325B\U0001325C\U0001325D\U00013282\U0001337A\U0001337B'
CLOSING_WALLED_CHARS = '\U00013287\U00013289'
CLOSING_CHARS = CLOSING_PLAIN_CHARS + CLOSING_WALLED_CHARS
CAP_CHARS = OPENING_CHARS + CLOSING_CHARS

OUTLINE = '\uE45C'
WALLED_OUTLINE = '\uE45D'

PLACEHOLDER = '\uFFFD'

OPEN_BRACKETS = '[{⟨⟦⸢'
CLOSE_BRACKETS = ']}⟩⟧⸣'

VARIATION_BASE = 0xFDFF
DAMAGE_BASE = 0x13446

INSERTION_PLACES = ['ts', 'bs', 'te', 'be', 'm', 't', 'b']
OVERLAY_INSERTION_PLACES = ['ts', 'bs', 'te', 'be']
INSERTION_CHARS = [INSERT_TS, INSERT_BS, INSERT_TE, INSERT_BE, \
					INSERT_M, INSERT_T, INSERT_B]

HIERO_FONT_NAME = 'NewGardiner'
HIERO_FONT_FILENAME = 'NewGardiner.ttf'

OUTLINE_THICKNESS = 0.11
WALLED_OUTLINE_THICKNESS = 0.13

def variation_to_num(s):
	return ord(s) - VARIATION_BASE

def num_to_variation(n):
	return chr(VARIATION_BASE + n) if n > 0 else ''

def damage_to_num(s):
	return ord(s) - DAMAGE_BASE

def num_to_damage(n):
	return chr(DAMAGE_BASE + n) if n > 0 else ''

def num_to_rotate(n):
	match n:
		case 1: return 90
		case 2: return 180
		case 3: return 270
		case 4: return 45
		case 5: return 135
		case 6: return 225
		case 7: return 315
		case _: return 0

def rotate_to_num(r):
	match r % 360:
		case 90: return 1
		case 180: return 2
		case 270: return 3
		case 45: return 4
		case 135: return 5
		case 225: return 6
		case 315: return 7
		case _: return 0

def rotate_char(ch):
	match ch:
		case '\uE45C': return '\uE462'
		case '\uE45D': return '\uE463'
		case '\U00013258': return '\uE464'
		case '\U00013259': return '\uE465'
		case '\U0001325A': return '\uE466'
		case '\U0001325B': return '\uE467'
		case '\U0001325C': return '\uE468'
		case '\U0001325D': return '\uE469'
		case '\U00013282': return '\uE46A'
		case '\U00013286': return '\uE46B' 
		case '\U00013287': return '\uE46C'
		case '\U00013288': return '\uE46D'
		case '\U00013289': return '\uE46E'
		case '\U00013379': return '\uE46F'
		case '\U0001337A': return '\uE470'
		case '\U0001337B': return '\uE471'
		case '\U0001342F': return '\uE472' 
		case _: return None

def place_to_char(pl):
	return INSERTION_CHARS[INSERTION_PLACES.index(pl)]

def insertion_position(pl, adjustments):
	match pl:
		case 'ts': x, y = 0, 0
		case 'bs': x, y = 0, 1
		case 'te': x, y = 1, 0
		case 'be': x, y = 1, 1
		case 't': x, y = 0.5, 0
		case 'b': x, y = 0.5, 1
		case _: x, y = 0.5, 0.5
	return adjustments.get_x(x), adjustments.get_y(y)

def mirror_place(pl):
	match pl:
		case 'ts': return 'te'
		case 'bs': return 'be'
		case 'te': return 'ts'
		case 'be': return 'bs'
		case _: return pl

def mirror_rotate(r):
	match r % 360:
		case 90: return 270
		case 180: return 180
		case 270: return 90
		case 45: return 315
		case 135: return 225
		case 225: return 135
		case 315: return 45
		case _: return 0

def quarter_mirror_rotate(r):
	return (mirror_rotate(r - 90) + 90) % 360

class Rectangle:
	def __init__(self, x, y, w, h):
		self.x = x
		self.y = y
		self.w = w
		self.h = h

	def __str__(self):
		return f'x={self.x} y={self.y} w={self.w} h={self.h}'

def damage_areas(damage, x0, x1, x2, y0, y1, y2):
	if damage == 15:
		return [Rectangle(x0, y0, x2-x0, y2-y0)]
	areas = []
	if damage & 1:
		areas.append(Rectangle(x0, y0, x1-x0, y1-y0))
	if damage & 2:
		areas.append(Rectangle(x0, y1, x1-x0, y2-y1))
	if damage & 4:
		areas.append(Rectangle(x1, y0, x2-x1, y1-y0))
	if damage & 8:
		areas.append(Rectangle(x1, y1, x2-x1, y2-y1))
	return areas
