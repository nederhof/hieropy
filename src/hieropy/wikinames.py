import csv
import importlib.resources as resources

NAME_FILE = 'namewiki.csv'
MNEMONIC_NAME_FILE = 'mnemonicnamewiki.csv'
COMBINATION_FILE = 'combinationwiki.csv'

_name_to_chars = None
_mnemonic_to_name = None
_combination_to_chars = None

def name_to_chars(name):
	if _name_to_chars is None:
		cache_name_and_chars()
	return _name_to_chars.get(name)

def mnemonic_to_name(mnemonic):
	if _mnemonic_to_name is None:
		cache_mnemonic()
	return _mnemonic_to_name.get(mnemonic)

def combination_to_chars(combination):
	if _combination_to_chars is None:
		cache_combination_and_chars()
	return _combination_to_chars.get(combination)

def cache_name_and_chars():
	global _name_to_chars
	_name_to_chars = {}
	with resources.files('hieropy.resources').joinpath(NAME_FILE).open('r', encoding='utf-8') as f:
		reader = csv.reader(f)
		for row in reader:
			n = row[0]
			p = row[1]
			_name_to_chars[n] = p

def cache_mnemonic():																			   
	global _mnemonic_to_name																		
	_mnemonic_to_name = {}																		  
	with resources.files('hieropy.resources').joinpath(MNEMONIC_NAME_FILE).open('r') as f:		  
		reader = csv.reader(f)																	  
		for row in reader:																		  
			if row[0][0] == '#':																	
				continue																			
			mnem = row[0]																		   
			name = row[1]																		   
			_mnemonic_to_name[mnem] = name

def cache_combination_and_chars():
	global _combination_to_chars
	_combination_to_chars = {}
	with resources.files('hieropy.resources').joinpath(COMBINATION_FILE).open('r', encoding='utf-8') as f:
		reader = csv.reader(f, delimiter=' ')
		for row in reader:
			if row[0][0] == '#':																	
				continue																			
			n = row[0]
			p = row[1]
			_combination_to_chars[n] = p

