import re
import ply.lex as lex
from ply.lex import TOKEN
import ply.yacc as yacc

from .wikinames import name_to_chars, mnemonic_to_name
from .wikistructure import Wiki, WikiLine, WikiVertical, WikiHorizontal, WikiSign, WikiBlank, \
		WikiEnclosure, WikiBracketOpen, WikiBracketClose, WikiText

tokens = (
	'BRACKET_OPEN',
	'BRACKET_CLOSE',
	'BREAK',
	'SIGN',
	'TEXT',
	'MIRROR',
	'FULL_BLANK',
	'HALF_BLANK',
	'BEGIN_ENCLOSURE',
	'END_ENCLOSURE',
	'SEP',
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

def t_BREAK(t):
	r'!'
	return t

def t_END_ENCLOSURE(t):
	r'-?[SFHsfh]?[0123]?>'
	return t

def t_SIGN(t):
	r'[0-9A-Za-z_&]+'
	if not name_to_chars(t.value) and not mnemonic_to_name(t.value) and not t.value in ['nswt','bity']:
		t.type = 'TEXT'
	return t

def t_TEXT1(t):
	r'\([0-9A-Za-z_]+(-[0-9A-Za-z_]+)+\)'
	t.type = 'TEXT'
	return t
def t_TEXT2(t):
	r'\([0-9A-Za-z_]+\)'
	if name_to_chars(t.value) or mnemonic_to_name(t.value) or t.value in ['nswt','bity']:
		t.type = 'SIGN'
	else:
		t.type = 'TEXT'
	return t

def t_MIRROR(t):
	r'\\'
	return t

def t_FULL_BLANK(t):
	r'\.\.'
	return t
def t_HALF_BLANK(t):
	r'\.'
	return t

def t_BEGIN_ENCLOSURE(t):
	r'<[SFHsfh]?[bme]?[0123]?-?'
	return t

def t_SEP(t):
	r'-[ \t\n\r\f]*|[ \t\n\r\f]+'
	return t

def t_COLON(t):
	r'::?'
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

# wiki
def p_wiki(p):
	'wiki : space lines'
	p[0] = Wiki(p[2])

# lines
def p_lines1(p):
	'lines : lines BREAK space line'
	p[0] = p[1] + [p[4]]
def p_lines2(p):
	'lines : line'
	p[0] = [p[1]]

# line
def p_line(p):
	'line : items'
	p[0] = WikiLine(p[1])

# items
def p_items1(p):
	'items : items item space'
	p[0] = p[1] + [p[2]]
def p_items2(p):
	'items :'
	p[0] = []

# item
def p_item1(p):
	'item : vertical'
	p[0] = p[1]
def p_item2(p):
	'item : enclosure'
	p[0] = p[1]
def p_item3(p):
	'item : BRACKET_OPEN'
	p[0] = WikiBracketOpen(p[1])
def p_item4(p):
	'item : BRACKET_CLOSE'
	p[0] = WikiBracketClose(p[1])
def p_item5(p):
	'item : TEXT'
	p[0] = WikiText(p[1])

# vertical
def p_vertical(p):
	'vertical : rows'
	p[0] = WikiVertical(p[1])

# rows
def p_rows1(p):
	'rows : rows COLON horizontal'
	p[0] = p[1] + [p[2], p[3]]
def p_rows2(p):
	'rows : horizontal'
	p[0] = [p[1]]

# horizontal
def p_horizontal(p):
	'horizontal : columns'
	p[0] = WikiHorizontal(p[1])
	
# columns
def p_columns1(p):
	'columns : columns ASTERISK basic'
	p[0] = p[1] + [p[3]]
def p_columns2(p):
	'columns : basic'
	p[0] = [p[1]]

# basic
def p_basic1(p):
	'basic : SIGN'
	p[0] = WikiSign(p[1], False)
def p_basic2(p):
	'basic : SIGN MIRROR'
	p[0] = WikiSign(p[1], True)
def p_basic3(p):
	'basic : FULL_BLANK'
	p[0] = WikiBlank(1)
def p_basic4(p):
	'basic : HALF_BLANK'
	p[0] = WikiBlank(0.5)
def p_basic5(p):
	'basic : OPEN vertical CLOSE'
	p[0] = p[2]

# enclosure
def p_enclosure(p):
	'enclosure : BEGIN_ENCLOSURE space enclosed_items END_ENCLOSURE'
	begin = p[1][1:].replace('-', '')
	end = p[4][:-1].replace('-', '')
	p[0] = WikiEnclosure(begin, p[3], end)

# enclosed_items
def p_enclosed_items1(p):
	'enclosed_items : enclosed_items vertical space'
	p[0] = p[1] + [p[2]]
def p_enclosed_items2(p):
	'enclosed_items :'
	p[0] = []

# space
def p_space1(p):
	'space :'
def p_space2(p):
	'space : space SEP'

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
	parser = yacc.yacc(tabmodule='wikiparsetab', write_tables=True, debug=False)
	return lexer, parser
