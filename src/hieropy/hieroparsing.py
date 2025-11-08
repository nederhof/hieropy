from . import unisyntax
from . import ressyntax

unilexer, uniparser = unisyntax.build_parser()
reslexer, resparser = ressyntax.build_parser()

class Parser:
	def __init__(self):
		self.last_error = None

	def parse(self, data):
		self.last_error = None
		self.lexer.lex_errors = None
		self.lexer.yacc_errors = None
		parsed = self.parser.parse(data, lexer=self.lexer)
		if self.lexer.lex_errors:
			self.last_error = self.lexer.lex_errors
		elif self.lexer.yacc_errors:
			self.last_error = self.lexer.yacc_errors
		else:
			self.last_error = ''
		return parsed

class UniParser(Parser):
	def __init__(self):
		super().__init__()
		self.lexer = unilexer
		self.parser = uniparser

class ResParser(Parser):
	def __init__(self):
		super().__init__()
		self.lexer = reslexer
		self.parser = resparser

