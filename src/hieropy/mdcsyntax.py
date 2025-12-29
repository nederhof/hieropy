import ply.lex as lex
from ply.lex import TOKEN
import ply.yacc as yacc

import re

from .mdcstructure import Line, Break, Text, LineNumber, Quadrat, Vertical, Horizontal, Complex, Overlay, \
	Ligature, Absolute, Sign, Blank, Lost, BracketOpen, BracketClose, Enclosure, Toggle

tokens = (
	'BRACKET_OPEN',
	'BRACKET_CLOSE',
	'BREAK',
	'TEXT',
	'LINE_NUMBER',
	'TAB',
	'ZONE',
	'WIDE_LOST',
	'TALL_LOST',
	'ARROW',
	'SIGN',
	'EQUALS',
	'ZONE_PRE',
	'ZONE_POST',
	'ABSOLUTE',
	'ABSOLUTE_CONTINUATION',
	'OMIT',
	'ROTATE_90',
	'ROTATE_180',
	'ROTATE_270',
	'ROTATE_90_MIRROR',
	'ROTATE_180_MIRROR',
	'ROTATE_270_MIRROR',
	'ROTATE_DEGREES',
	'SCALE_PERCENTAGE',
	'RED_GLYPH',
	'GRAY_GLYPH',
	'ELONGATE_GLYPH',
	'GLYPH_SHADE',
	'MIRROR',
	'IGNORED_MODIFIER',
	'FULL_BLANK',
	'HALF_BLANK',
	'LOST',
	'HALF_LOST',
	'QUADRAT_SHADE',
	'SHADE_ON',
	'SHADE_OFF',
	'SHADE_FULL',
	'SHADE_HALF',
	'SHADE_WIDE',
	'SHADE_TALL',
	'OVERLAY_DOUBLE',
	'OVERLAY_SINGLE',
	'RED',
	'BLACK',
	'COLOR_TOGGLE',
	'SHADE_TOGGLE',
	'BEGIN_ENCLOSURE',
	'END_ENCLOSURE',
	'SEP',
	'SPACE',
	'LACUNA',
	'LIGATURE',
	'COLON',
	'ASTERISK',
	'OPEN',
	'CLOSE',
)

def t_BRACKET_OPEN(t):
	r'\[[&{\[\\"\'(?]'
	return t
def t_BRACKET_CLOSE(t): 
	r'[&}\]\\"\'\)?]\]'
	return t

def t_BREAK1(t):
	r'!![ \t\n\r\f_]*'
	t.type = 'BREAK'
	return t
def t_BREAK2(t):
	r'(\+s-)?!(=[0-9]+%)?[ \t\n\r\f_]*'
	t.type = 'BREAK'
	return t
def t_BREAK3(t):
	r'\+s[ \t\n\r\f_]*'
	t.type = 'BREAK'
	return t
def t_TEXT1(t):
	r'\+[a-rt-z+S](\\\\\+|\\\+|[^+])*'
	t.type = 'TEXT'
	return t
def t_TEXT2(t):
	r'@[^-]*[\n\r\f]?'
	t.type = 'TEXT'
	return t
def t_LINE_NUMBER(t):
	r'\|[^|-]*'
	return t
def t_BREAK4(t):
	r'\{[lL][0-9]+,[0-9]+\}'
	t.type = 'BREAK'
	return t
def t_TAB(t):
	r'(\?[0-9]+\ *|%clear|%\{[^}]*\})'
	return t
def t_ZONE(t):
	r'zone\{[^}]*\}'
	return t

def t_WIDE_LOST(t):
	r'h/'
	return t
def t_TALL_LOST(t):
	r'v/'
	return t

def t_ARROW(t):
	r'PF[0-9]-'
	return t

def t_SIGN(t):
	r'([A-Z]|Aa|Ff|NL|NU)[0-9]+[A-Za-z]*|[a-zA-Z]+|US[0-9A-Z]*|[0-9]+|"([^"]+)"|`'
	return t

def t_EQUALS(t):
	r'='
	return t

def t_ZONE_PRE(t):
	r'\^{2,3}'
	return t
def t_ZONE_POST(t):
	r'&{2,3}'
	return t
def t_ABSOLUTE(t):
	r'\{\{[0-9]+,[0-9]+,[0-9]+\}\}'
	return t
def t_ABSOLUTE_CONTINUATION(t):
	r'\*\*'
	return t

def t_OMIT(t):
	r'\^'
	return t

def t_ROTATE_270(t):
	r'\\r1'
	return t
def t_ROTATE_180(t):
	r'\\r2'
	return t
def t_ROTATE_90(t):
	r'\\r3'
	return t
def t_IGNORED_MODIFIER1(t):
	r'\\r4'
	t.type = 'IGNORED_MODIFIER'
	return t
def t_ROTATE_270_MIRROR(t):
	r'\\t1'
	return t
def t_ROTATE_180_MIRROR1(t):
	r'\\t2'
	t.type = 'ROTATE_180_MIRROR'
	return t
def t_ROTATE_90_MIRROR(t):
	r'\\t3'
	return t
def t_MIRROR1(t):
	r'\\t4'
	t.type = 'MIRROR'
	return t
def t_MIRROR2(t):
	r'\\t'
	t.type = 'MIRROR'
	return t
def t_ROTATE_DEGREES(t):
	r'\\R[0-9]+'
	return t
def t_SCALE_PERCENTAGE(t):
	r'\\[0-9]+'
	return t

def t_RED_GLYPH(t):
	r'\\red'
	return t
def t_GRAY_GLYPH(t):
	r'\\i'
	return t
def t_ELONGATE_GLYPH(t):
	r'\\l'
	return t
def t_GLYPH_SHADE(t):
	r'\\shading[1234]+'
	return t
def t_MIRROR3(t):
	r'\\h'
	t.type = 'MIRROR'
	return t
def t_ROTATE_180_MIRROR2(t):
	r'\\v'
	t.type = 'ROTATE_180_MIRROR'
	return t
def t_IGNORED_MODIFIER2(t):
	r'\\[A-Za-z]+[0-9]*'
	t.type = 'IGNORED_MODIFIER'
	return t
def t_MIRROR4(t):
	r'\\'
	t.type = 'MIRROR'
	return t

def t_FULL_BLANK(t):
	r'\.\.'
	return t
def t_HALF_BLANK(t):
	r'\.'
	return t
def t_LOST(t):
	r'//'
	return t
def t_HALF_LOST(t):
	r'/'
	return t

def t_QUADRAT_SHADE(t):
	r'\#[1234]+'
	return t

def t_SHADE_ON(t):
	r'-?\#b'
	return t
def t_SHADE_OFF(t):
	r'-?\#e'
	return t

def t_SHADE_FULL(t):
	r'\#//'
	return t
def t_SHADE_HALF(t):
	r'\#/'
	return t
def t_SHADE_WIDE(t):
	r'\#h/'
	return t
def t_SHADE_TALL(t):
	r'\#v/'
	return t

def t_OVERLAY_DOUBLE(t):
	r'\#\#'
	return t
def t_OVERLAY_SINGLE(t):
	r'\#'
	return t

def t_RED(t):
	r'\$r'
	return t
def t_BLACK(t):
	r'\$b'
	return t
def t_COLOR_TOGGLE(t):
	r'\$'
	return t
def t_SHADE_TOGGLE(t):
	r'(- ?)?\#'
	return t

#           cartouche
#  S        serekh
#  H        Hwt
#  F        walled enclosure without caps
#  0   0    plain cartouche without caps
#  1   0    round cap at start
#  2   0    knot at start
# h0   h1   Hwt missing start cap, no square
# h2   h3   Hwt, square at bottom and square at top
# s2   1    reverse serekh
def t_BEGIN_ENCLOSURE(t):
	r'<[SFHsfh]?[bme]?[0123]?- ?'
	return t
def t_END_ENCLOSURE(t):
	r'-[SFHsfh]?[0123]?>'
	return t

def t_SEP(t):
	r'-[ \t\n\r\f_]*'
	return t
def t_SPACE(t):
	r'[ \t\n\r\f_]+'
	return t

def t_LACUNA(t):
	r'\?{1,2}'
	return t

def t_LIGATURE(t):
	r'&'
	return t

def t_COLON(t):
	r':'
	return t
def t_ASTERISK(t):
	r'\*'
	return t
def t_OPEN(t):
	r'\('
	return t
def t_CLOSE(t):
	r'\)'
	return t

def t_error(t):
	t.lexer.lex_errors = f'Illegal character {t.value[0]!r}'
	t.lexer.skip(1)

# mdc
def p_mdc(p):
	'mdc : space top_items'
	p[0] = Line(p[2])

# top_items
def p_top_items1(p):
	'top_items : seps'
	p[0] = [p[1]]
def p_top_items2(p):
	'top_items : top_items top_item seps'
	p[0] = p[1] + [p[2], p[3]]

# seps
def p_seps1(p):
	'seps :'
	p[0] = Toggle({})
def p_seps2(p):
	'seps : seps sep'
	p[0] = p[1].update(p[2])

# sep
def p_sep1(p):
	'sep : SEP'
	p[0] = {}
def p_sep2(p):
	'sep : toggle'
	p[0] = p[1]

# top_item
def p_top_item1(p):
	'top_item : BREAK'
	p[0] = Break(p[1])
def p_top_item2(p):
	'top_item : TEXT'
	p[0] = Text(p[1])
def p_top_item3(p):
	'top_item : LINE_NUMBER'
	p[0] = LineNumber(p[1][1:])
def p_top_item4(p):
	'top_item : ARROW'
	p[0] = None
def p_top_item5(p):
	'top_item : TAB'
	p[0] = None
def p_top_item6(p):
	'top_item : LACUNA'
	p[0] = None
def p_top_item7(p):
	'top_item : OMIT'
	p[0] = None
def p_top_item8(p):
	'top_item : ZONE'
	p[0] = None
def p_top_item9(p):
	'top_item : quadrat'
	p[0] = p[1]

# quadrat
def p_quadrat(p):
	'quadrat : vertical_group group_shading'
	p[0] = Quadrat(Vertical(p[1]), p[2])

# group_shading
def p_group_shading1(p):
	'group_shading :'
	p[0] = corners('')
def p_group_shading2(p):
	'group_shading : quadrat_shade space'
	p[0] = p[1]

# quadrat_shade
def p_quadrat_shade(p):
	'quadrat_shade : QUADRAT_SHADE'
	p[0] = corners(p[1])

# vertical_group
def p_vertical_group1(p):
	'vertical_group : horizontal_group'
	p[0] = [Horizontal(p[1])]
def p_vertical_group2(p):
	'vertical_group : vertical_group COLON horizontal_group'
	p[0] = p[1] + [Horizontal(p[3])]

# horizontal_group
def p_horizontal_group1(p):
	'horizontal_group : horizontal_element'
	p[0] = [p[1]]
def p_horizontal_group2(p):
	'horizontal_group : horizontal_group ASTERISK horizontal_element'
	p[0] = p[1] + [p[3]]

# horizontal_element
def p_horizontal_element1(p):
	'horizontal_element : inner_group ZONE_PRE hieroglyph ZONE_POST inner_group'
	p[0] = Complex(p[1], p[3], p[5])
def p_horizontal_element2(p):
	'horizontal_element : inner_group ZONE_PRE hieroglyph'
	p[0] = Complex(p[1], p[3], None)
def p_horizontal_element3(p):
	'horizontal_element : hieroglyph ZONE_POST inner_group'
	p[0] = Complex(None, p[1], p[3])
def p_horizontal_element4(p):
	'horizontal_element : inner_group'
	p[0] = p[1]

# inner_group
def p_inner_group1(p):
	'inner_group : hieroglyph'
	p[0] = p[1]
def p_inner_group2(p):
	'inner_group : overlay'
	p[0] = p[1]
def p_inner_group3(p):
	'inner_group : ligature'
	p[0] = Ligature(p[1])
def p_inner_group4(p):
	'inner_group : absolute'
	p[0] = Absolute(p[1])
def p_inner_group5(p):
	'inner_group : OPEN top_items CLOSE space'
	p[0] = Vertical(p[2])

# overlay
def p_overlay1(p):
	'overlay : hieroglyph OVERLAY_SINGLE hieroglyph'
	p[0] = Overlay(p[1], p[3])
def p_overlay2(p):
	'overlay : hieroglyph OVERLAY_DOUBLE hieroglyph'
	p[0] = Overlay(p[1], p[3])

# ligature
def p_ligature1(p):
	'ligature : hieroglyph LIGATURE hieroglyph'
	p[0] = [p[1], p[3]]
def p_ligature2(p):
	'ligature : ligature LIGATURE hieroglyph'
	p[0] = p[1] + [p[3]]

# absolute
def p_absolute1(p):
	'absolute : hieroglyph ABSOLUTE_CONTINUATION hieroglyph'
	p[0] = [p[1], p[3]]
def p_absolute2(p):
	'absolute : absolute ABSOLUTE_CONTINUATION hieroglyph'
	p[0] = p[1] + [p[3]]

# hieroglyph
def p_hieroglyph1(p):
	'hieroglyph : grammar sign modifiers placement space'
	p[0] = p[2].set_modifiers_and_placement(p[3], p[4])
def p_hieroglyph2(p):
	'hieroglyph : enclosure modifiers placement space'
	p[0] = p[1].set_modifiers_and_placement(p[2], p[3])

# space
def p_space1(p):
	'space :'
def p_space2(p):
	'space : SPACE'

# sign
def p_sign1(p):
	'sign : SIGN'
	p[0] = Sign(p[1], None, None)
def p_sign2(p):
	'sign : FULL_BLANK'
	p[0] = Blank(1, None, None)
def p_sign3(p):
	'sign : HALF_BLANK'
	p[0] = Blank(0.5, None, None)
def p_sign4(p):
	'sign : LOST'
	p[0] = Lost(1, 1, None, None)
def p_sign5(p):
	'sign : HALF_LOST'
	p[0] = Lost(0.5, 0.5, None, None)
def p_sign6(p):
	'sign : TALL_LOST'
	p[0] = Lost(0.5, 1, None, None)
def p_sign7(p):
	'sign : WIDE_LOST'
	p[0] = Lost(1, 0.5, None, None)
def p_sign8(p):
	'sign : SHADE_FULL'
	p[0] = Lost(1, 1, None, None)
def p_sign9(p):
	'sign : SHADE_HALF'
	p[0] = Lost(0.5, 0.5, None, None)
def p_sign10(p):
	'sign : SHADE_WIDE'
	p[0] = Lost(1, 0.5, None, None)
def p_sign11(p):
	'sign : SHADE_TALL'
	p[0] = Lost(0.5, 1, None, None)
def p_sign12(p):
	'sign : BRACKET_OPEN'
	p[0] = BracketOpen(p[1], None, None)
def p_sign13(p):
	'sign : BRACKET_CLOSE'
	p[0] = BracketClose(p[1], None, None)

# placement
def p_placement1(p):
	'placement :'
	p[0] = None
def p_placement2(p):
	'placement : ABSOLUTE'
	p[0] = absolute_position(p[1])

# grammar
def p_grammar1(p):
	'grammar :'
def p_grammar2(p):
	'grammar : EQUALS'

# enclosure
def p_enclosure(p):
	'enclosure : begin_enclosure top_items end_enclosure'
	p[0] = Enclosure(p[1], p[2], p[3], None, None)

# begin_enclosure
def p_begin_enclosure(p):
	'begin_enclosure : BEGIN_ENCLOSURE'
	p[0] = p[1][1:-1]

# end_enclosure
def p_end_enclosure(p):
	'end_enclosure : END_ENCLOSURE'
	p[0] = p[1][1:-1]

# modifiers
def p_modifiers1(p):
	'modifiers :'
	p[0] = {}
def p_modifiers2(p):
	'modifiers : modifiers modifier'
	modifiers_new = p[1].copy()
	modifiers_new.update(p[2])
	p[0] = modifiers_new

# modifier
def p_modifier1(p):
	'modifier : MIRROR'
	p[0] = { 'mirror': True }
def p_modifier2(p):
	'modifier : ROTATE_90'
	p[0] = { 'rotate': 90 }
def p_modifier3(p):
	'modifier : ROTATE_180'
	p[0] = { 'rotate': 180 }
def p_modifier4(p):
	'modifier : ROTATE_270'
	p[0] = { 'rotate': 270 }
def p_modifier5(p):
	'modifier : ROTATE_90_MIRROR'
	p[0] = { 'rotate': 90, 'mirror': True }
def p_modifier6(p):
	'modifier : ROTATE_180_MIRROR'
	p[0] = { 'rotate': 180, 'mirror': True }
def p_modifier7(p):
	'modifier : ROTATE_270_MIRROR'
	p[0] = { 'rotate': 270, 'mirror': True }
def p_modifier8(p):
	'modifier : ROTATE_DEGREES'
	p[0] = { 'rotate': int(p[1][2:]) }
def p_modifier9(p):
	'modifier : SCALE_PERCENTAGE'
	p[0] = {}
def p_modifier10(p):
	'modifier : RED_GLYPH'
	p[0] = { 'color': 'red' }
def p_modifier11(p):
	'modifier : GRAY_GLYPH'
	p[0] = { 'color': 'gray' }
def p_modifier12(p):
	'modifier : ELONGATE_GLYPH'
	p[0] = { 'elongate': True }
def p_modifier13(p):
	'modifier : GLYPH_SHADE'
	p[0] = { 'shade': corners(p[1]) }
def p_modifier14(p):
	'modifier : SHADE_FULL'
	p[0] = { 'shade': corners('1234') }
def p_modifier17(p):
	'modifier : SHADE_HALF'
	p[0] = { 'shade': corners('1') }
def p_modifier18(p):
	'modifier : SHADE_WIDE'
	p[0] = { 'shade': corners('12') }
def p_modifier19(p):
	'modifier : SHADE_TALL'
	p[0] = { 'shade': corners('13') }
def p_modifier20(p):
	'modifier : IGNORED_MODIFIER'
	p[0] = {}

# toggle
def p_toggle1(p):
	'toggle : COLOR_TOGGLE'
	p[0] = { 'color': 'toggle' }
def p_toggle2(p):
	'toggle : RED'
	p[0] = { 'color': 'red' }
def p_toggle3(p):
	'toggle : BLACK'
	p[0] = { 'color': 'black' }
def p_toggle4(p):
	'toggle : SHADE_TOGGLE'
	p[0] = { 'shade': 'toggle' }
def p_toggle5(p):
	'toggle : SHADE_ON'
	p[0] = { 'shade': 'on' }
def p_toggle6(p):
	'toggle : SHADE_OFF'
	p[0] = { 'shade': 'off' }
def p_toggle7(p):
	'toggle : OVERLAY_SINGLE'
	p[0] = { 'shade': 'toggle' }

def absolute_position(s):
	matched = re.match(r'^{{([0-9]+),([0-9]+),([0-9]+)}}$', s)
	if matched:
		x, y, s = map(int, matched.groups())
		return { 'x': x, 'y': y, 's': s }
	else:
		return None

def corners(s):
	return { 'ts': '1' in s, 'te': '2' in s, 'bs': '3' in s, 'be': '4' in s }

def p_error(p):
	if p:
		lexer.yacc_errors = f'Syntax error at position {p.lexpos}'
	else:
		lexer.yacc_errors = 'Unexpected end of input'

lexer = None

def build_parser():
	global lexer
	lexer = lex.lex()
	lexer.lex_errors = None
	lexer.yacc_errors = None
	parser = yacc.yacc(tabmodule='mdcparsetab', write_tables=True, debug=False)
	return lexer, parser
