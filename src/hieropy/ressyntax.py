import ply.lex as lex
from ply.lex import TOKEN
import ply.yacc as yacc

from .resstructure import Fragment, Hiero, VerGroup, VerSubgroup, HorGroup, HorSubgroup, \
	Namedglyph, Emptyglyph, Box, Stack, Insert, Modify, Note, Switch, Arg

tokens = (
	'EMPTY',
	'STACK',
	'INSERT',
	'MODIFY',
	'GLYPH_NAME',
	'NAME',
	'SHORT_STRING',
	'LONG_STRING',
	'REAL',
	'NAT',
	'MINUS',
	'COLON',
	'OPEN',
	'CLOSE',
	'ASTERISK',
	'PERIOD',
	'COMMA',
	'CARET',
	'EXCLAM',
	'SQ_OPEN',
	'SQ_CLOSE',
	'EQUALS',
	'WHITESPACE',
)

t_EMPTY		= 'empty'
t_STACK		= 'stack'
t_INSERT	= 'insert'
t_MODIFY	= 'modify'

def t_GLYPH_NAME(t):
	r'([A-IK-Z]|NL|NU|Aa)[1-9][0-9]{0,2}[a-z]{0,2}'
	return t

def t_NAME(t):
	r'[a-zA-Z]+'
	if t.value == 'empty':
		t.type = 'EMPTY'
	elif t.value == 'stack':
		t.type = 'STACK'
	elif t.value == 'insert':
		t.type = 'INSERT'
	elif t.value == 'modify':
		t.type = 'MODIFY'
	return t

t_SHORT_STRING	= '"([^\\t\\n\\r\\f"\\\\]|\\\\"|\\\\\\\\)"'
t_LONG_STRING	= '"([^\\t\\n\\r\\f"\\\\]|\\\\"|\\\\\\\\){2,}"'
t_REAL			= '[0-9]?\\.[0-9]{1,2}'
t_NAT			= '0|[1-9][0-9]{0,2}'

t_MINUS			= '-'
t_COLON			= ':'
t_OPEN			= '\\('
t_CLOSE			= '\\)'
t_ASTERISK		= '\\*'
t_PERIOD		= '\\.'
t_COMMA			= ','
t_CARET			= '\\^'
t_EXCLAM		= '!'
t_SQ_OPEN		= '\\['
t_SQ_CLOSE		= '\\]'
t_EQUALS		= '='
t_WHITESPACE	= '[ \\t\\n\\r\\f]'

def t_error(t):
	t.lexer.lex_errors = "Illegal character '%s'" % t.value[0]
	t.lexer.skip(1)

lexer = lex.lex()

# fragment
def p_fragment(p):
	'fragment : whitespaces opt_header switches opt_hieroglyphic'
	p[0] = Fragment(p[2],p[3],p[4])

# opt_header
def p_opt_header1(p):
	'opt_header :'
	p[0] = []
def p_opt_header2(p):
	'opt_header : header'
	p[0] = p[1]

# header
def p_header(p):
	'header : arg_bracket_list whitespaces'
	p[0] = p[1]

# opt_hieroglyphic
def p_opt_hieroglyphic1(p):
	'opt_hieroglyphic :'
	p[0] = None
def p_opt_hieroglyphic2(p):
	'opt_hieroglyphic : hieroglyphic'
	p[0] = p[1]

# hieroglyphic
def p_hieroglyphic1(p):
	'hieroglyphic : top_group'
	p[0] = Hiero(p[1])
def p_hieroglyphic2(p):
	'hieroglyphic : hieroglyphic MINUS opt_arg_bracket_list ws top_group'
	p[0] = p[1].add_group(p[3], p[4], p[5])

# top_group
def p_top_group1(p):
	'top_group : ver_group'
	p[0] = p[1]
def p_top_group2(p):
	'top_group : hor_group'
	p[0] = p[1]
def p_top_group3(p):
	'top_group : basic_group'
	p[0] = p[1]

# ver_group
def p_ver_group1(p):
	'ver_group : ver_subgroup COLON opt_arg_bracket_list ws ver_subgroup'
	p[0] = VerGroup(p[1], p[3], p[4], p[5])
def p_ver_group2(p):
	'ver_group : ver_group COLON opt_arg_bracket_list ws ver_subgroup'
	p[0] = p[1].add_group(p[3], p[4], p[5])

# ver_subgroup
def p_ver_subgroup1(p):
	'ver_subgroup : hor_group'
	p[0] = VerSubgroup(Switch([]), p[1], Switch([]))
def p_ver_subgroup2(p):
	'ver_subgroup : OPEN ws hor_group CLOSE ws'
	p[0] = VerSubgroup(p[2], p[3], p[5])
def p_ver_subgroup3(p):
	'ver_subgroup : basic_group'
	p[0] = VerSubgroup(Switch([]), p[1], Switch([]))

# hor_group
def p_hor_group1(p):
	'hor_group : hor_subgroup ASTERISK opt_arg_bracket_list ws hor_subgroup'
	p[0] = HorGroup(p[1], p[3], p[4], p[5])
def p_hor_group2(p):
	'hor_group : hor_group ASTERISK opt_arg_bracket_list ws hor_subgroup'
	p[0] = p[1].add_group(p[3], p[4], p[5])

# hor_subgroup
def p_hor_subgroup1(p):
	'hor_subgroup : OPEN ws ver_group CLOSE ws'
	p[0] = HorSubgroup(p[2], p[3], p[5])
def p_hor_subgroup2(p):
	'hor_subgroup : basic_group'
	p[0] = HorSubgroup(Switch([]), p[1], Switch([]))

# basic_group
def p_basic_group1(p):
	'basic_group : named_glyph'
	p[0] = p[1]
def p_basic_group2(p):
	'basic_group : empty_glyph'
	p[0] = p[1]
def p_basic_group3(p):
	'basic_group : box'
	p[0] = p[1]
def p_basic_group4(p):
	'basic_group : stack'
	p[0] = p[1]
def p_basic_group5(p):
	'basic_group : insert'
	p[0] = p[1]
def p_basic_group6(p):
	'basic_group : modify'
	p[0] = p[1]

# named_glyph
def p_named_glyph1(p):
	'named_glyph : glyph_name opt_arg_bracket_list whitespaces notes switches'
	p[0] = Namedglyph(p[1], p[2], p[4], p[5])
def p_named_glyph2(p):
	'named_glyph : name opt_arg_bracket_list whitespaces notes switches'
	p[0] = Namedglyph(p[1], p[2], p[4], p[5])
def p_named_glyph3(p):
	'named_glyph : nat opt_arg_bracket_list whitespaces notes switches'
	p[0] = Namedglyph(str(p[1]), p[2], p[4], p[5])
def p_named_glyph4(p):
	'named_glyph : short_string opt_arg_bracket_list whitespaces notes switches'
	p[0] = Namedglyph(p[1], p[2], p[4], p[5])

# empty_glyph
def p_empty_glyph1(p):
	'empty_glyph : EMPTY opt_arg_bracket_list whitespaces opt_note switches'
	p[0] = Emptyglyph(p[2], p[4], p[5])
def p_empty_glyph2(p):
	'empty_glyph : PERIOD whitespaces opt_note switches'
	p[0] = Emptyglyph(Emptyglyph.point_args(), p[3], p[4])

# box
def p_box(p):
	'box : name opt_arg_bracket_list whitespaces OPEN ws opt_hieroglyphic CLOSE whitespaces notes switches'
	p[0] = Box(p[1], p[2], p[5], p[6], p[9], p[10])

# stack
def p_stack(p):
	'stack : STACK opt_arg_bracket_list whitespaces OPEN ws top_group COMMA ws top_group CLOSE ws'
	p[0] = Stack(p[2], p[5], p[6], p[8], p[9], p[11])

# insert
def p_insert(p):
	'insert : INSERT opt_arg_bracket_list whitespaces OPEN ws top_group COMMA ws top_group CLOSE ws'
	p[0] = Insert(p[2], p[5], p[6], p[8], p[9], p[11])

# modify
def p_modify(p):
	'modify : MODIFY opt_arg_bracket_list whitespaces OPEN ws top_group CLOSE ws'
	p[0] = Modify(p[2], p[5], p[6], p[8])

# opt_note
def p_opt_note1(p):
	'opt_note :'
	p[0] = None
def p_opt_note2(p):
	'opt_note : note'
	p[0] = p[1]

# notes
def p_notes1(p):
	'notes :'
	p[0] = []
def p_notes2(p):
	'notes : notes note'
	p[0] = p[1] + [p[2]]

# note
def p_note(p):
	'note : CARET string opt_arg_bracket_list whitespaces'
	p[0] = Note(p[2], p[3])

# ws
def p_ws(p):
	'ws : whitespaces switches'
	p[0] = p[2]

# switches
def p_switches1(p):
	'switches :'
	p[0] = Switch([])
def p_switches2(p):
	'switches : switch switches'
	p[0] = p[1].join(p[2])

# switch
def p_switch(p):
	'switch : EXCLAM opt_arg_bracket_list whitespaces'
	p[0] = Switch(p[2])

# opt_arg_bracket_list
def p_opt_arg_bracket_list1(p):
	'opt_arg_bracket_list :'
	p[0] = []
def p_opt_arg_bracket_list2(p):
	'opt_arg_bracket_list : arg_bracket_list'
	p[0] = p[1]

# arg_bracket_list
def p_arg_bracket_list(p):
	'arg_bracket_list : SQ_OPEN whitespaces opt_arg_list SQ_CLOSE'
	p[0] = p[3]

# opt_arg_list
def p_opt_arg_list1(p):
	'opt_arg_list :'
	p[0] = []
def p_opt_arg_list2(p):
	'opt_arg_list : arg_list'
	p[0] = p[1]

# arg_list
def p_arg_list1(p):
	'arg_list : arg whitespaces'
	p[0] = [p[1]]
def p_arg_list2(p):
	'arg_list : arg_list COMMA whitespaces arg whitespaces'
	p[0] = p[1] + [p[4]]

# arg
def p_arg1(p):
	'arg : name EQUALS name'
	p[0] = Arg(p[1], p[3])
def p_arg2(p):
	'arg : name EQUALS nat'
	p[0] = Arg(p[1], p[3])
def p_arg3(p):
	'arg : name EQUALS real'
	p[0] = Arg(p[1], p[3])
def p_arg4(p):
	'arg : name'
	p[0] = Arg(p[1], None)
def p_arg5(p):
	'arg : nat'
	p[0] = Arg(p[1], None)
def p_arg6(p):
	'arg : real'
	p[0] = Arg(p[1], None)

# whitespaces
def p_whitespaces1(p):
	'whitespaces :'
def p_whitespaces2(p):
	'whitespaces : whitespaces WHITESPACE'

# glyph_name
def p_glyph_name(p):
	'glyph_name : GLYPH_NAME'
	p[0] = p[1]

# name
def p_name(p):
	'name : NAME'
	p[0] = p[1]

# short_string
def p_short_string(p):
	'short_string : SHORT_STRING'
	p[0] = p[1]

# string
def p_string1(p):
	'string : LONG_STRING'
	p[0] = p[1]
def p_string2(p):
	'string : SHORT_STRING'
	p[0] = p[1]

# real
def p_real(p):
	'real : REAL'
	p[0] = float(p[1])

# nat
def p_nat(p):
	'nat : NAT'
	p[0] = int(p[1])

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
	parser = yacc.yacc(tabmodule='resparsetab', write_tables=True, debug=False)
	return lexer, parser
