from . import unisyntax

unilexer, uniparser = unisyntax.build_parser()

class UniParser:
	def __init__(self):
		self.last_error = None

	def parse(self, data):
		self.last_error = None
		unilexer.lex_errors = None
		unilexer.yacc_errors = None
		parsed = uniparser.parse(data, lexer=unilexer)
		if unilexer.lex_errors:
			self.last_error = unilexer.lex_errors
		elif unilexer.yacc_errors:
			self.last_error = unilexer.yacc_errors
		else:
			self.last_error = ''
		return parsed
