import re
import ply.lex as lex
from ply.lex import TOKEN
import ply.yacc as yacc

from .uniconstants import *
from .unistructure import Fragment, Vertical, Horizontal, Enclosure, Basic, Overlay, \
	Literal, Singleton, Blank, Lost, BracketOpen, BracketClose

tokens = (
	'BRACKET_OPEN',
	'BRACKET_CLOSE',
	'VS',
	'SIGN',
	'VER',
	'HOR',
	'INSERT_TS',
	'INSERT_BS',
	'INSERT_TE',
	'INSERT_BE',
	'OVERLAY',
	'BEGIN_SEGMENT',
	'END_SEGMENT',
	'INSERT_M',
	'INSERT_T',
	'INSERT_B',
	'MIRROR',
	'FULL_BLANK',
	'HALF_BLANK',
	'FULL_LOST',
	'HALF_LOST',
	'TALL_LOST',
	'WIDE_LOST',
	'ENCLOSURE_OPENING',
	'ENCLOSURE_CLOSING',
	'DELIMITER',
	'DAMAGED',
)

OPENING_CHAR = '[' + OPENING_CHARS + ']'
CLOSING_CHAR = '[' + CLOSING_CHARS + ']'
DAMAGED_CHAR = '[\U00013447-\U00013455]'
BEGIN_ENCLOSURE_CHAR = '[\U0001343C\U0001343E]'
END_ENCLOSURE_CHAR = '[\U0001343D\U0001343F]'
ENCLOSURE_OPENING = '(' + OPENING_CHAR + DAMAGED_CHAR + '?)?' + BEGIN_ENCLOSURE_CHAR
ENCLOSURE_CLOSING = END_ENCLOSURE_CHAR + '(' + CLOSING_CHAR + DAMAGED_CHAR + '?)?'

t_BRACKET_OPEN = '[\\[{⟨⟦⸢]'
t_BRACKET_CLOSE = '[\\]}⟩⟧⸣]'
t_VS	= '[\uFE00-\uFE06]'
t_SIGN	= '[\U00013000-\U00013257\U0001325E-\U00013281\U00013283-\U00013285\U0001328A-\U00013378\U0001337C-\U0001342E\U00013460-\U000143FA' + \
		PLACEHOLDER + ']'

t_VER           = VER
t_HOR           = HOR
t_INSERT_TS     = INSERT_TS
t_INSERT_BS     = INSERT_BS
t_INSERT_TE     = INSERT_TE
t_INSERT_BE     = INSERT_BE
t_OVERLAY       = OVERLAY
t_BEGIN_SEGMENT = BEGIN_SEGMENT
t_END_SEGMENT   = END_SEGMENT
t_INSERT_M      = INSERT_M
t_INSERT_T      = INSERT_T
t_INSERT_B      = INSERT_B
t_MIRROR        = MIRROR
t_FULL_BLANK    = FULL_BLANK
t_HALF_BLANK    = HALF_BLANK
t_FULL_LOST     = FULL_LOST
t_HALF_LOST     = HALF_LOST
t_TALL_LOST     = TALL_LOST
t_WIDE_LOST     = WIDE_LOST

@TOKEN(ENCLOSURE_OPENING)
def t_ENCLOSURE_OPENING(t):
	return t

@TOKEN(ENCLOSURE_CLOSING)
def t_ENCLOSURE_CLOSING(t):
	return t

t_DELIMITER = OPENING_CHAR + '|' + CLOSING_CHAR
t_DAMAGED = DAMAGED_CHAR

# errors = {'message': None}

def t_error(t):
	t.lexer.lex_errors = "Illegal character '%s'" % t.value[0]
	t.lexer.skip(1)

lexer = lex.lex(reflags=re.UNICODE)

# fragment
def p_fragment(p):
	'fragment : top_groups'
	p[0] = Fragment(p[1])

# top_groups
def p_top_groups1(p):
	'top_groups :'
	p[0] = []
def p_top_groups2(p):
	'top_groups : group top_groups'
	p[0] = [p[1]] + p[2]
def p_top_groups3(p):
	'top_groups : singleton_group top_groups'
	p[0] = [p[1]] + p[2]

# groups
def p_groups1(p):
	'groups :'
	p[0] = []
def p_groups2(p):
	'groups : group groups'
	p[0] = [p[1]] + p[2]

# group
def p_group1(p):
	'group : vertical_group'
	p[0] = p[1]
def p_group2(p):
	'group : horizontal_group'
	p[0] = p[1]
def p_group3(p):
	'group : basic_group'
	p[0] = p[1]
def p_group4(p):
	'group : literal'
	p[0] = p[1]

# vertical_group
def p_vertical_group(p):
	'vertical_group : ver_subgroup rest_ver_group'
	p[0] = Vertical([p[1]] + p[2])

# opt_rest_ver_group
def p_opt_rest_ver_group1(p):
	'opt_rest_ver_group :'
	p[0] = []
def p_opt_rest_ver_group2(p):
	'opt_rest_ver_group : rest_ver_group'
	p[0] = p[1]

# rest_ver_group
def p_rest_ver_group(p):
	'rest_ver_group : VER ver_subgroup opt_rest_ver_group'
	p[0] = [p[2]] + p[3]
	
# br_vertical_group
def p_br_vertical_group(p):
	'br_vertical_group : BEGIN_SEGMENT ver_subgroup rest_br_ver_group'
	p[0] = Vertical([p[2]] + p[3])

# opt_rest_br_ver_group
def p_opt_rest_br_ver_group1(p):
	'opt_rest_br_ver_group : END_SEGMENT'
	p[0] = []
def p_opt_rest_br_ver_group2(p):
	'opt_rest_br_ver_group : rest_br_ver_group'
	p[0] = p[1]

# rest_br_ver_group
def p_rest_br_ver_group(p):
	'rest_br_ver_group : VER ver_subgroup opt_rest_br_ver_group'
	p[0] = [p[2]] + p[3]

# br_flat_vertical_group
def p_br_flat_vertical_group(p):
	'br_flat_vertical_group : BEGIN_SEGMENT literal rest_br_flat_ver_group'
	p[0] = [p[2]] + p[3]

# rest_br_flat_ver_group
def p_rest_br_flat_ver_group1(p):
	'rest_br_flat_ver_group : VER literal rest_br_flat_ver_group'
	p[0] = [p[2]] + p[3]
def p_rest_br_flat_ver_group2(p):
	'rest_br_flat_ver_group : VER literal END_SEGMENT'
	p[0] = [p[2]]

# ver_subgroup
def p_ver_subgroup1(p):
	'ver_subgroup : horizontal_group'
	p[0] = p[1]
def p_ver_subgroup2(p):
	'ver_subgroup : basic_group'
	p[0] = p[1]
def p_ver_subgroup3(p):
	'ver_subgroup : literal'
	p[0] = p[1]
	
# horizontal_group
def p_horizontal_group1(p):
	'horizontal_group : hor_subgroup rest_hor_group'
	p[0] = Horizontal([p[1]] + p[2])
def p_horizontal_group2(p):
	'horizontal_group : literal rest_hor_group'
	p[0] = Horizontal([p[1]] + p[2])
def p_horizontal_group3(p):
	'horizontal_group : bracket_open hor_subgroup opt_bracket_close opt_rest_hor_group'
	p[0] = Horizontal([p[1],p[2]] + p[3] + p[4])
def p_horizontal_group4(p):
	'horizontal_group : bracket_open literal opt_bracket_close opt_rest_hor_group'
	p[0] = Horizontal([p[1],p[2]] + p[3] + p[4])
def p_horizontal_group5(p):
	'horizontal_group : hor_subgroup bracket_close opt_rest_hor_group'
	p[0] = Horizontal([p[1],p[2]] + p[3])
def p_horizontal_group6(p):
	'horizontal_group : literal bracket_close opt_rest_hor_group'
	p[0] = Horizontal([p[1],p[2]] + p[3])

# opt_rest_hor_group
def p_opt_rest_hor_group1(p):
	'opt_rest_hor_group :'
	p[0] = []
def p_opt_rest_hor_group2(p):
	'opt_rest_hor_group : rest_hor_group'
	p[0] = p[1]

# rest_hor_group
def p_rest_hor_group1(p):
	'rest_hor_group : HOR hor_subgroup opt_rest_hor_group'
	p[0] = [p[2]] + p[3]
def p_rest_hor_group2(p):
	'rest_hor_group : HOR literal opt_rest_hor_group'
	p[0] = [p[2]] + p[3]
def p_rest_hor_group3(p):
	'rest_hor_group : HOR bracket_open hor_subgroup opt_bracket_close opt_rest_hor_group'
	p[0] = [p[2],p[3]] + p[4] + p[5]
def p_rest_hor_group4(p):
	'rest_hor_group : HOR bracket_open literal opt_bracket_close opt_rest_hor_group'
	p[0] = [p[2],p[3]] + p[4] + p[5]
def p_rest_hor_group5(p):
	'rest_hor_group : HOR hor_subgroup bracket_close opt_rest_hor_group'
	p[0] = [p[2],p[3]] + p[4]
def p_rest_hor_group6(p):
	'rest_hor_group : HOR literal bracket_close opt_rest_hor_group'
	p[0] = [p[2],p[3]] + p[4]

# br_horizontal_group
def p_br_horizontal_group1(p):
	'br_horizontal_group : BEGIN_SEGMENT hor_subgroup rest_br_hor_group'
	p[0] = Horizontal([p[2]] + p[3])
def p_br_horizontal_group2(p):
	'br_horizontal_group : BEGIN_SEGMENT literal rest_br_hor_group'
	p[0] = Horizontal([p[2]] + p[3])
def p_br_horizontal_group3(p):
	'br_horizontal_group : BEGIN_SEGMENT bracket_open hor_subgroup opt_bracket_close opt_rest_br_hor_group'
	p[0] = Horizontal([p[2],p[3]] + p[4] + p[5])
def p_br_horizontal_group4(p):
	'br_horizontal_group : BEGIN_SEGMENT bracket_open literal opt_bracket_close opt_rest_br_hor_group'
	p[0] = Horizontal([p[2],p[3]] + p[4] + p[5])
def p_br_horizontal_group5(p):
	'br_horizontal_group : BEGIN_SEGMENT hor_subgroup bracket_close opt_rest_br_hor_group'
	p[0] = Horizontal([p[2],p[3]] + p[4])
def p_br_horizontal_group6(p):
	'br_horizontal_group : BEGIN_SEGMENT literal bracket_close opt_rest_br_hor_group'
	p[0] = Horizontal([p[2],p[3]] + p[4])

# opt_rest_br_hor_group
def p_opt_rest_br_hor_group1(p):
	'opt_rest_br_hor_group : END_SEGMENT'
	p[0] = []
def p_opt_rest_br_hor_group2(p):
	'opt_rest_br_hor_group : rest_br_hor_group'
	p[0] = p[1]

# rest_br_hor_group
def p_rest_br_hor_group1(p):
	'rest_br_hor_group : HOR hor_subgroup opt_rest_br_hor_group'
	p[0] = [p[2]] + p[3]
def p_rest_br_hor_group2(p):
	'rest_br_hor_group : HOR literal opt_rest_br_hor_group'
	p[0] = [p[2]] + p[3]
def p_rest_br_hor_group3(p):
	'rest_br_hor_group : HOR bracket_open hor_subgroup opt_bracket_close opt_rest_br_hor_group'
	p[0] = [p[2],p[3]] + p[4] + p[5]
def p_rest_br_hor_group4(p):
	'rest_br_hor_group : HOR bracket_open literal opt_bracket_close opt_rest_br_hor_group'
	p[0] = [p[2],p[3]] + p[4] + p[5]
def p_rest_br_hor_group5(p):
	'rest_br_hor_group : HOR hor_subgroup bracket_close opt_rest_br_hor_group'
	p[0] = [p[2],p[3]] + p[4]
def p_rest_br_hor_group6(p):
	'rest_br_hor_group : HOR literal bracket_close opt_rest_br_hor_group'
	p[0] = [p[2],p[3]] + p[4]

# br_flat_horizontal_group
def p_br_flat_horizontal_group(p):
	'br_flat_horizontal_group : BEGIN_SEGMENT literal rest_br_flat_hor_group'
	p[0] = [p[2]] + p[3]

# rest_br_flat_hor_group
def p_rest_br_flat_hor_group1(p):
	'rest_br_flat_hor_group : HOR literal rest_br_flat_hor_group'
	p[0] = [p[2]] + p[3]
def p_rest_br_flat_hor_group2(p):
	'rest_br_flat_hor_group : HOR literal END_SEGMENT'
	p[0] = [p[2]]

# hor_subgroup
def p_hor_subgroup1(p):
	'hor_subgroup : br_vertical_group'
	p[0] = p[1]
def p_hor_subgroup2(p):
	'hor_subgroup : basic_group'
	p[0] = p[1]

# basic_group
def p_basic_group1(p):
	'basic_group : core_group'
	p[0] = p[1]
def p_basic_group2(p):
	'basic_group : insertion_group'
	p[0] = p[1]
def p_basic_group3(p):
	'basic_group : placeholder'
	p[0] = p[1]
def p_basic_group4(p):
	'basic_group : enclosure'
	p[0] = p[1]

# insertion_group
def p_insertion_group1(p):
	'insertion_group : core_group insertion'
	p[0] = Basic(p[1], p[2])
def p_insertion_group2(p):
	'insertion_group : literal insertion'
	p[0] = Basic(p[1], p[2])

# br_insertion_group
def p_br_insertion_group1(p):
	'br_insertion_group : BEGIN_SEGMENT core_group insertion END_SEGMENT'
	p[0] = Basic(p[2], p[3])
def p_br_insertion_group2(p):
	'br_insertion_group : BEGIN_SEGMENT literal insertion END_SEGMENT'
	p[0] = Basic(p[2], p[3])

# insertion
def p_insertion1(p):
	'insertion : INSERT_TS in_subgroup opt_bs_insertion opt_te_insertion opt_be_insertion opt_m_insertion opt_t_insertion opt_b_insertion'
	p[0] = {'ts': p[2], 'bs': p[3], 'te': p[4], 'be': p[5], 'm': p[6], 't': p[7], 'b': p[8]}
def p_insertion2(p):
	'insertion : INSERT_BS in_subgroup opt_te_insertion opt_be_insertion opt_m_insertion opt_t_insertion opt_b_insertion'
	p[0] = {'bs': p[2], 'te': p[3], 'be': p[4], 'm': p[5], 't': p[6], 'b': p[7]}
def p_insertion3(p):
	'insertion : INSERT_TE in_subgroup opt_be_insertion opt_m_insertion opt_t_insertion opt_b_insertion'
	p[0] = {'te': p[2], 'be': p[3], 'm': p[4], 't': p[5], 'b': p[6]}
def p_insertion4(p):
	'insertion : INSERT_BE in_subgroup opt_m_insertion opt_t_insertion opt_b_insertion'
	p[0] = {'be': p[2], 'm': p[3], 't': p[4], 'b': p[5]}
def p_insertion5(p):
	'insertion : INSERT_M in_subgroup opt_t_insertion opt_b_insertion'
	p[0] = {'m': p[2], 't': p[3], 'b': p[4]}
def p_insertion6(p):
	'insertion : INSERT_T in_subgroup opt_b_insertion'
	p[0] = {'t': p[2], 'b': p[3]}
def p_insertion7(p):
	'insertion : INSERT_B in_subgroup'
	p[0] = {'b': p[2]}

# opt_bs_insertion
def p_opt_bs_insertion1(p):
	'opt_bs_insertion :'
	p[0] = None
def p_opt_bs_insertion2(p):
	'opt_bs_insertion : INSERT_BS in_subgroup'
	p[0] = p[2]

# opt_te_insertion
def p_opt_te_insertion1(p):
	'opt_te_insertion :'
	p[0] = None
def p_opt_te_insertion2(p):
	'opt_te_insertion : INSERT_TE in_subgroup'
	p[0] = p[2]

# opt_be_insertion
def p_opt_be_insertion1(p):
	'opt_be_insertion :'
	p[0] = None
def p_opt_be_insertion2(p):
	'opt_be_insertion : INSERT_BE in_subgroup'
	p[0] = p[2]

# opt_m_insertion
def p_opt_m_insertion1(p):
	'opt_m_insertion :'
	p[0] = None
def p_opt_m_insertion2(p):
	'opt_m_insertion : INSERT_M in_subgroup'
	p[0] = p[2]

# opt_t_insertion
def p_opt_t_insertion1(p):
	'opt_t_insertion :'
	p[0] = None
def p_opt_t_insertion2(p):
	'opt_t_insertion : INSERT_T in_subgroup'
	p[0] = p[2]

# opt_b_insertion
def p_opt_b_insertion1(p):
	'opt_b_insertion :'
	p[0] = None
def p_opt_b_insertion2(p):
	'opt_b_insertion : INSERT_B in_subgroup'
	p[0] = p[2]

# in_subgroup
def p_in_subgroup1(p):
	'in_subgroup : br_vertical_group'
	p[0] = p[1]
def p_in_subgroup2(p):
	'in_subgroup : br_horizontal_group'
	p[0] = p[1]
def p_in_subgroup3(p):
	'in_subgroup : br_insertion_group'
	p[0] = p[1]
def p_in_subgroup4(p):
	'in_subgroup : core_group'
	p[0] = p[1]
def p_in_subgroup5(p):
	'in_subgroup : literal'
	p[0] = p[1]
def p_in_subgroup6(p):
	'in_subgroup : placeholder'
	p[0] = p[1]
def p_in_subgroup7(p):
	'in_subgroup : enclosure'
	p[0] = p[1]

# core_group
def p_core_group(p):
	'core_group : flat_horizontal_group OVERLAY flat_vertical_group'
	p[0] = Overlay(p[1], p[3])

# flat_horizontal_group
def p_flat_horizontal_group1(p):
	'flat_horizontal_group : br_flat_horizontal_group'
	p[0] = p[1]
def p_flat_horizontal_group2(p):
	'flat_horizontal_group : literal'
	p[0] = [p[1]]

# flat_vertical_group
def p_flat_vertical_group1(p):
	'flat_vertical_group : br_flat_vertical_group'
	p[0] = p[1]
def p_flat_vertical_group2(p):
	'flat_vertical_group : literal'
	p[0] = [p[1]]

# bracket_open
def p_bracket_open(p):
	'bracket_open : BRACKET_OPEN'
	p[0] = BracketOpen(p[1])

# bracket_close
def p_bracket_close(p):
	'bracket_close : BRACKET_CLOSE'
	p[0] = BracketClose(p[1])

# opt_bracket_close
def p_opt_bracket_close1(p):
	'opt_bracket_close :'
	p[0] = []
def p_opt_bracket_close2(p):
	'opt_bracket_close : BRACKET_CLOSE'
	p[0] = [BracketClose(p[1])]

# literal
def p_literal(p):
	'literal : sign opt_vs opt_mirror opt_damaged'
	p[0] = Literal(p[1], p[2], p[3], p[4])

# sign
def p_sign(p):
	'sign : SIGN'
	p[0] = p[1]

# opt_vs
def p_opt_vs1(p):
	'opt_vs :'
	p[0] = 0
def p_opt_vs2(p):
	'opt_vs : VS'
	p[0] = variation_to_num(p[1])

# opt_mirror
def p_opt_mirror1(p):
	'opt_mirror :'
	p[0] = False
def p_opt_mirror2(p):
	'opt_mirror : MIRROR'
	p[0] = True

# placeholder
def p_placeholder1(p):
	'placeholder : FULL_BLANK'
	p[0] = Blank(1)
def p_placeholder2(p):
	'placeholder : HALF_BLANK'
	p[0] = Blank(0.5)
def p_placeholder3(p):
	'placeholder : FULL_LOST opt_vs'
	p[0] = Lost(1, 1, p[2])
def p_placeholder4(p):
	'placeholder : HALF_LOST opt_vs'
	p[0] = Lost(0.5, 0.5, p[2])
def p_placeholder5(p):
	'placeholder : TALL_LOST opt_vs'
	p[0] = Lost(0.5, 1, p[2])
def p_placeholder6(p):
	'placeholder : WIDE_LOST opt_vs'
	p[0] = Lost(1, 0.5, p[2])

# enclosure
def p_enclosure(p):
	'enclosure : opening groups closing'
	p[0] = Enclosure('walled' if p[1]['type'] == BEGIN_WALLED_ENCLOSURE else 'plain', p[2], \
			p[1]['delimiter'], p[1]['damage'], p[3]['delimiter'], p[3]['damage'])

# opening
def p_opening(p):
	'opening : ENCLOSURE_OPENING'
	p[0] = parse_opening(p[1])

# closing
def p_closing(p):
	'closing : ENCLOSURE_CLOSING'
	p[0] = parse_closing(p[1])

# singleton_group
def p_singleton_group(p):
	'singleton_group : delimiter opt_damaged'
	p[0] = Singleton(p[1], p[2])

# delimiter
def p_delimiter(p):
	'delimiter : DELIMITER'
	p[0] = p[1]

# opt_damaged
def p_opt_damaged1(p):
	'opt_damaged :'
	p[0] = 0
def p_opt_damaged2(p):
	'opt_damaged : DAMAGED'
	p[0] = damage_to_num(p[1])

def p_error(p):
	if p:
		lexer.yacc_errors = f'Syntax error at position {p.lexpos}'
	else:
		lexer.yacc_errors = 'Unexpected end of input'

def parse_opening(s):
	chars = list(s)
	if len(chars) == 1:
		return {'delimiter': None, 'damage': 0, 'type': chars[0]}
	elif len(chars) == 2:
		return {'delimiter': chars[0], 'damage': 0, 'type': chars[1]}
	else:
		return {'delimiter': chars[0], 'damage': damage_to_num(chars[1]), 'type': chars[2]}

def parse_closing(s):
	chars = list(s)
	if len(chars) == 1:
		return {'type': chars[0], 'delimiter': None, 'damage': 0}
	elif len(chars) == 2:
		return {'type': chars[0], 'delimiter': chars[1], 'damage': 0}
	else:
		return {'type': chars[0], 'delimiter': chars[1], 'damage': damage_to_num(chars[2])}

lexer = None

def build_parser():
	global lexer
	lexer = lex.lex()
	lexer.lex_errors = None
	lexer.yacc_errors = None
	parser = yacc.yacc(tabmodule='uniparsetab', write_tables=True, debug=False)
	return lexer, parser
