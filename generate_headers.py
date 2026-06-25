import os
import re
import shutil
import sys

try:
	import cpp_demangle
except ImportError:
	print("Error: cpp_demangle package not found. Please install it using 'pip install cpp_demangle'")
	exit(1)

def find_main_paren(s):
	s_clean = re.sub(r'operator\s*(<=>|<<|>>|<=|>=|->|<|>)', 'operator_HIDDEN', s)
	depth = 0
	for i, c in enumerate(s_clean):
		if c == '<': depth += 1
		elif c == '>': depth -= 1
		elif c == '(' and depth == 0: return i
	return -1

def split_namespace(s):
	parts = []
	depth = 0
	last_idx = 0
	s_clean = re.sub(r'operator\s*(<=>|<<|>>|<=|>=|->|<|>)', 'operator_HIDDEN', s)
	i = 0
	while i < len(s):
		if s_clean[i] == '<': depth += 1
		elif s_clean[i] == '>': depth -= 1
		elif depth == 0 and s[i] == ':' and i+1 < len(s) and s[i+1] == ':':
			parts.append(s[last_idx:i])
			last_idx = i + 2
			i += 1
		i += 1
	parts.append(s[last_idx:])
	return parts

def strip_return_type(s):
	depth = 0
	for i in range(len(s)-1, -1, -1):
		if s[i] == '>': depth += 1
		elif s[i] == '<': depth -= 1
		elif s[i] == ')': depth += 1
		elif s[i] == '(': depth -= 1
		elif s[i] == ']': depth += 1
		elif s[i] == '[': depth -= 1
		elif s[i] == ' ' and depth == 0:
			return s[i+1:]
	return s

def parse_demangled(demangled, mangled):
	if '_ZZ' in mangled or '_ZGVZ' in mangled:
		m = re.search(r'^_[A-Za-z]*?N.*?(\d+)', mangled)
		if m:
			length = int(m.group(1))
			start = m.end()
			file_name = mangled[start:start+length]
			if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', file_name):
				return file_name, ''
		return 'global', ''

	if any(x in demangled for x in ['vtable for', 'VTT for', 'typeinfo']):
		m = re.search(r'(vtable for|typeinfo for|typeinfo name for|VTT for)\s+(.*)', demangled)
		if m:
			class_str = m.group(2).strip()
			parts = split_namespace(class_str)
			if len(parts) > 0:
				first_part = parts[0]
				file_name = re.sub(r'[^A-Za-z0-9_~]', '', first_part.split('<')[0])
				if len(parts) > 1:
					if '<' in first_part:
						class_name = '::'.join([first_part] + parts[1:])
					else:
						class_name = '::'.join(parts[1:])
				else:
					class_name = ''
				return file_name, class_name
		return 'global', ''

	paren_idx = find_main_paren(demangled)
	base = demangled[:paren_idx] if paren_idx != -1 else demangled

	base = strip_return_type(base)
	parts = split_namespace(base)

	if len(parts) > 1:
		first_part = parts[0]
		file_name = re.sub(r'[^A-Za-z0-9_~]', '', first_part.split('<')[0])

		if '<' in first_part:
			class_name = '::'.join([first_part] + parts[1:-1])
		else:
			class_name = '::'.join(parts[1:-1])
		return file_name, class_name
	else:
		return 'global', ''

def format_decl(ns_path, demangled, mangled, indent):

	is_secondary = False
	if re.search(r'(C2|C3|D0|D2)[A-Za-z0-9_]*$', mangled):
		is_secondary = True

	if any(x in demangled for x in ['guard variable', 'vtable for', 'VTT for', 'typeinfo']):
		return f"{indent}// {demangled} // {mangled}"

	if '_ZZ' in mangled or '_ZGVZ' in mangled:
		return f"{indent}// local static: {demangled} // {mangled}"

	decl = demangled

	paren_idx = find_main_paren(decl)
	if paren_idx == -1:

		field_name = decl.split('::')[-1]
		decl_str = f"static void* {field_name};"
		if is_secondary:
			return f"{indent}// {decl_str} // {mangled}"
		return f"{indent}{decl_str} // {mangled}"

	before_paren = decl[:paren_idx]
	after_paren = decl[paren_idx:]

	depth = 0
	valid_colon_idx = -1
	for i in range(len(before_paren)-1, 0, -1):
		if before_paren[i] == '>':
			depth += 1
		elif before_paren[i] == '<':
			depth -= 1
		elif depth == 0 and before_paren[i] == ':' and before_paren[i-1] == ':':
			valid_colon_idx = i - 1
			break

	if valid_colon_idx != -1:
		depth = 0
		space_idx = -1
		for i in range(valid_colon_idx-1, -1, -1):
			if before_paren[i] == '>':
				depth += 1
			elif before_paren[i] == '<':
				depth -= 1
			elif depth == 0 and before_paren[i] == ' ':
				space_idx = i
				break

		if space_idx != -1 and 'operator' not in before_paren[space_idx:]:
			return_type = before_paren[:space_idx+1]
		else:
			return_type = ''

		function_name = before_paren[valid_colon_idx+2:]
		decl = return_type + function_name + after_paren

	paren_idx = find_main_paren(decl)
	before_paren_stripped = decl[:paren_idx].strip() if paren_idx != -1 else decl

	class_basename = ns_path.split('::')[-1] if ns_path else ""

	is_constructor = before_paren_stripped == class_basename
	is_destructor = before_paren_stripped == '~' + class_basename
	is_operator = 'operator' in before_paren_stripped
	has_return_type = ' ' in before_paren_stripped or '*' in before_paren_stripped or '&' in before_paren_stripped

	if not is_constructor and not is_destructor and not is_operator and not has_return_type:
		base_func_name = before_paren_stripped.split('<')[0]

		bool_prefixes = ('is', '_is', 'contains', '_contains', 'includes', '_includes', 'has', '_has', 'can', '_can', 'should', '_should', 'was', '_was')
		voidptr_prefixes = ('get', '_get')

		if matches_prefix(base_func_name, voidptr_prefixes):
			decl = "void* " + decl
		elif matches_prefix(base_func_name, bool_prefixes):
			decl = "bool " + decl
		else:
			decl = "void " + decl

	if not decl.endswith(";"):
		decl += ";"

	if is_secondary:
		return f"{indent}// {decl} // {mangled}"
	return f"{indent}{decl} // {mangled}"

def matches_prefix(name, prefixes):
	for p in prefixes:
		if name.startswith(p):
			if len(name) == len(p):
				return True
			next_char = name[len(p)]
			if next_char.isupper() or next_char == '_' or next_char.isdigit():
				return True
	return False

def get_sort_key(mangled, demangled, class_name):
	if any(x in demangled for x in ['guard variable', 'vtable for', 'VTT for', 'typeinfo']):
		return (1, "", "", demangled)
	if '_ZZ' in mangled or '_ZGVZ' in mangled:
		return (1, "", "", demangled)

	paren_idx = find_main_paren(demangled)
	if paren_idx == -1:
		return (2, "", "", demangled)

	base = strip_return_type(demangled[:paren_idx])
	parts = split_namespace(base)
	base_func_name = parts[-1].split('<')[0]
	class_basename = class_name.split('::')[-1] if class_name else ""

	if base_func_name == class_basename:
		return (3, "", "", demangled)

	if base_func_name == '~' + class_basename:
		return (4, "", "", demangled)

	bool_prefs = ('is', '_is', 'contains', '_contains', 'includes', '_includes', 'has', '_has', 'can', '_can', 'should', '_should', 'was', '_was')
	if matches_prefix(base_func_name, bool_prefs):
		prop = base_func_name
		for p in bool_prefs:
			if base_func_name.startswith(p):
				prop = base_func_name[len(p):].lstrip('_')
				break
		return (5, prop, base_func_name, demangled)

	getset_prefs = ('get', '_get', 'set', '_set')
	if matches_prefix(base_func_name, getset_prefs):
		prop = base_func_name
		for p in getset_prefs:
			if base_func_name.startswith(p):
				prop = base_func_name[len(p):].lstrip('_')
				break
		return (6, prop, base_func_name, demangled)

	if base_func_name.startswith('operator'):
		return (8, base_func_name, base_func_name, demangled)

	return (7, base_func_name, base_func_name, demangled)

def clean_type_names(name):
	name = name.replace('std::__ndk1::basic_string<char, std::__ndk1::char_traits<char>, std::__ndk1::allocator<char> >', 'stl_string')
	name = name.replace('std::__ndk1::basic_string<char, std::__ndk1::char_traits<char>, std::__ndk1::allocator<char>>', 'stl_string')

	name = re.sub(r'std::__ndk1::vector<(.*?),\s*std::__ndk1::allocator<\1\s*>\s*>', r'stl_vector<\1>', name)
	name = re.sub(r'std::__ndk1::unique_ptr<(.*?),\s*std::__ndk1::default_delete<\1\s*>\s*>', r'stl_unique_ptr<\1>', name)

	name = name.replace('std::__ndk1::', 'stl_')
	return name

def main():
	if len(sys.argv) > 1:
		arch = sys.argv[1]
		input_file = f"lib{arch}-symbols.txt"
		output_dir = f"{arch}-symbols"
	else:
		input_file = "minecraftpe.txt"
		output_dir = "symbols"

	if not os.path.exists(input_file):
		print(f"Error: {input_file} not found.")
		return

	if os.path.exists(output_dir):
		bak_dir = output_dir + ".bak"
		if os.path.exists(bak_dir):
			try:
				shutil.rmtree(bak_dir)
			except Exception:
				pass
		try:
			os.rename(output_dir, bak_dir)
			print(f"Moved existing '{output_dir}' to '{bak_dir}'")
		except Exception:
			print(f"Warning: Could not rename '{output_dir}' to '{bak_dir}'. Overwriting in place.")

	os.makedirs(output_dir, exist_ok=True)

	file_map = {}
	file_needs_stl = {}

	print(f"Reading symbols from {input_file}...")

	with open(input_file, 'r', encoding='utf-8') as f:
		for line in f:
			mangled = line.strip()
			if not mangled: continue

			try:
				demangled = cpp_demangle.demangle(mangled)
			except Exception:
				demangled = mangled

			orig_file_name, _ = parse_demangled(demangled, mangled)
			if orig_file_name in ('std', '__cxxabiv1', '__gnu_cxx'):
				continue

			demangled = clean_type_names(demangled)

			file_name, class_name = parse_demangled(demangled, mangled)

			if not file_name:
				file_name = "global"

			if file_name not in file_map:
				file_map[file_name] = {}
			if class_name not in file_map[file_name]:
				file_map[file_name][class_name] = []

			file_map[file_name][class_name].append((mangled, demangled))

			if 'stl_' in demangled:
				file_needs_stl[file_name] = True

	print(f"Found {len(file_map)} files to generate.")
	print(f"Generating headers in '{output_dir}'...")

	for file_name, classes in file_map.items():
		safe_file_name = "".join(c for c in file_name if c.isalnum() or c == '_')
		if not safe_file_name:
			safe_file_name = "global"

		header_path = os.path.join(output_dir, f"{safe_file_name}.h")

		with open(header_path, 'w', encoding='utf-8') as f:
			f.write("#pragma once\n\n")

			if file_needs_stl.get(file_name, False) or file_needs_stl.get(safe_file_name, False):
				f.write("#include <stl.h>\n\n")

			if safe_file_name == "global":
				for class_name, syms in classes.items():
					for mangled, demangled in syms:
						f.write(format_decl("", demangled, mangled, "") + "\n")
				continue

			has_nested = any(c for c in classes.keys())

			is_class = not has_nested
			for mangled, demangled in classes.get("", []):
				if any(x in demangled for x in ['typeinfo', 'vtable', 'VTT']):
					is_class = True
					break
				category = get_sort_key(mangled, demangled, safe_file_name)[0]
				if category in (3, 4):
					is_class = True
					break

			if not is_class:
				f.write(f"namespace {safe_file_name} {{\n\n")
				indent = "\t"
			else:
				f.write(f"class {safe_file_name} {{\n")
				f.write("public:\n")
				indent = "\t"

			tree = {'__syms__': [], '__sub__': {}}
			for class_name, syms in classes.items():
				current = tree
				if class_name:
					parts = split_namespace(class_name)
					for p in parts:
						if p not in current['__sub__']:
							current['__sub__'][p] = {'__syms__': [], '__sub__': {}}
						current = current['__sub__'][p]
				current['__syms__'].extend(syms)

			def write_node(node, current_indent, path_parts):
				syms = node['__syms__']

				full_ns_path = file_name
				if path_parts:
					full_ns_path += "::" + "::".join(path_parts)

				syms.sort(key=lambda x: get_sort_key(x[0], x[1], full_ns_path))

				for mangled, demangled in syms:
					decl_str = format_decl(full_ns_path, demangled, mangled, current_indent)
					f.write(f"{decl_str}\n")

				for sub_name, sub_node in node['__sub__'].items():
					if '<' in sub_name:
						f.write(f"\n{current_indent}template<>\n")
						f.write(f"{current_indent}class {sub_name} {{\n")
					else:
						f.write(f"\n{current_indent}class {sub_name} {{\n")
					f.write(f"{current_indent}public:\n")
					write_node(sub_node, current_indent + "\t", path_parts + [sub_name])
					f.write(f"{current_indent}}};\n")

			write_node(tree, indent, [])

			if not is_class:
				f.write("}\n")
			else:
				f.write("};\n")

	print("Header generation completed.")

if __name__ == '__main__':
	main()
