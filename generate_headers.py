import os
import re
import shutil
import sys
import json
import glob
from collections import defaultdict

CONSTANT_METHODS = {}

try:
	import cpp_demangle
except ImportError:
	print("Error: cpp_demangle package not found. Please install it using \"pip install cpp_demangle\"")
	exit(1)

def find_main_paren(s):
	s_clean = re.sub(r"operator\s*(<=>|<<|>>|<=|>=|->|<|>)", "operator_HIDDEN", s)
	depth = 0
	for i, c in enumerate(s_clean):
		if c == "<": depth += 1
		elif c == ">": depth -= 1
		elif c == "(" and depth == 0: return i
	return -1

def split_namespace(s):
	parts = []
	depth = 0
	last_idx = 0
	s_clean = re.sub(r"operator\s*(<=>|<<|>>|<=|>=|->|<|>)", "operator_HIDDEN", s)
	i = 0
	while i < len(s):
		c = s_clean[i]
		if c in "<([{": depth += 1
		elif c in ">)]}": depth -= 1
		elif depth == 0 and s[i] == ":" and i+1 < len(s) and s[i+1] == ":":
			parts.append(s[last_idx:i])
			last_idx = i + 2
			i += 1
		i += 1
	parts.append(s[last_idx:])
	return parts

def strip_return_type(s):
	depth = 0
	for i in range(len(s)-1, -1, -1):
		if s[i] == ">": depth += 1
		elif s[i] == "<": depth -= 1
		elif s[i] == ")": depth += 1
		elif s[i] == "(": depth -= 1
		elif s[i] == "]": depth += 1
		elif s[i] == "[": depth -= 1
		elif s[i] == " " and depth == 0:
			return s[i+1:]
	return s

def parse_demangled(demangled, mangled):
	if "_ZZ" in mangled or "_ZGVZ" in mangled:
		m = re.search(r"^_([A-Za-z]*?)N.*?(\d+)", mangled)
		file_name = "global"
		if m:
			length = int(m.group(2))
			start = m.end()
			extracted = mangled[start:start+length]
			if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", extracted):
				file_name = extracted

		paren_idx = find_main_paren(demangled)
		base = demangled[:paren_idx] if paren_idx != -1 else demangled
		base = strip_return_type(base)
		parts = split_namespace(base)

		valid_parts = []
		for p in parts[:-1]:
			if "(" in p or "{" in p: break
			valid_parts.append(p)

		class_name = ""
		if len(valid_parts) > 0:
			if valid_parts[0] == file_name:
				class_name = "::".join(valid_parts[1:])
			else:
				class_name = "::".join(valid_parts)

		return file_name, class_name

	if any(x in demangled for x in ["vtable for", "VTT for", "typeinfo"]):
		m = re.search(r"(vtable for|typeinfo for|typeinfo name for|VTT for)\s+(.*)", demangled)
		if m:
			class_str = m.group(2).strip()
			parts = split_namespace(class_str)
			if len(parts) > 0:
				first_part = parts[0]
				file_name = re.sub(r"[^A-Za-z0-9_~]", "", first_part.split("<")[0])
				if len(parts) > 1:
					if "<" in first_part:
						class_name = "::".join([first_part] + parts[1:])
					else:
						class_name = "::".join(parts[1:])
				else:
					class_name = ""
				return file_name, class_name
		return "global", ""

	paren_idx = find_main_paren(demangled)
	base = demangled[:paren_idx] if paren_idx != -1 else demangled

	base = strip_return_type(base)
	parts = split_namespace(base)

	if len(parts) > 1:
		first_part = parts[0]
		file_name = re.sub(r"[^A-Za-z0-9_~]", "", first_part.split("<")[0])

		if "<" in first_part:
			class_name = "::".join([first_part] + parts[1:-1])
		else:
			class_name = "::".join(parts[1:-1])
		return file_name, class_name
	else:
		return "global", ""

def format_decl(ns_path, demangled, mangled, indent, is_virtual=False):
	format_decl.override_type = None
	format_decl.last_const_val = None
	is_secondary = False
	if re.search(r"(C2|C3|D0|D2)[A-Za-z0-9_]*$", mangled):
		is_secondary = True

	if any(x in demangled for x in ["guard variable", "vtable for", "VTT for", "typeinfo"]):
		return f"{indent}// {demangled} // {mangled}"

	if "_ZZ" in mangled or "_ZGVZ" in mangled:
		display_name = demangled
		if ns_path and display_name.startswith(ns_path + "::"):
			display_name = display_name[len(ns_path)+2:]
		return f"{indent}// local static {display_name}; // {mangled}"

	decl = demangled

	paren_idx = find_main_paren(decl)
	if paren_idx == -1:
		field_name = decl.split("::")[-1]
		decl_str = f"static void* {field_name};"
		if is_secondary:
			return f"{indent}// {decl_str} // {mangled}"
		return f"{indent}{decl_str} // {mangled}"

	before_paren = decl[:paren_idx]
	after_paren = decl[paren_idx:]

	depth = 0
	valid_colon_idx = -1
	s_clean = re.sub(r"operator\s*(<=>|<<|>>|<=|>=|->|<|>)", "operator_HIDDEN", before_paren)
	for i in range(len(before_paren)-1, 0, -1):
		if s_clean[i] == ">":
			depth += 1
		elif s_clean[i] == "<":
			depth -= 1
		elif depth == 0 and before_paren[i] == ":" and before_paren[i-1] == ":":
			valid_colon_idx = i - 1
			break

	if valid_colon_idx != -1:
		depth = 0
		space_idx = -1
		for i in range(valid_colon_idx-1, -1, -1):
			if s_clean[i] == ">":
				depth += 1
			elif s_clean[i] == "<":
				depth -= 1
			elif depth == 0 and before_paren[i] == " ":
				space_idx = i
				break

		if space_idx != -1 and "operator" not in before_paren[space_idx:]:
			return_type = before_paren[:space_idx+1]
		else:
			return_type = ""

		function_name = before_paren[valid_colon_idx+2:]
		decl = return_type + function_name + after_paren

		actual_full_func = function_name
		if valid_colon_idx != -1:
			last_space = before_paren.rfind(" ", 0, valid_colon_idx)
			actual_full_func = before_paren[last_space+1:] if last_space != -1 else before_paren

		full_func = actual_full_func
		if full_func not in CONSTANT_METHODS:
			full_func = f"{ns_path}::{function_name}"

		if full_func in CONSTANT_METHODS:
			const_val = CONSTANT_METHODS[full_func]
			bool_prefixes = ("is", "_is", "contains", "_contains", "includes", "_includes", "has", "_has", "can", "_can", "should", "_should", "was", "_was")
			func_base = actual_full_func.split("::")[-1]
			is_bool = "bool" in return_type or func_base.startswith(bool_prefixes) or const_val in ("0", "1")

			if is_bool:
				const_val = "true" if const_val != "0" else "false"
				format_decl.override_type = "bool"
			elif "*" in return_type and const_val == "0":
				const_val = "nullptr"
			elif const_val == "0" and func_base.startswith(("get", "_get")) and not return_type:
				const_val = "nullptr"
				format_decl.override_type = "void*"
			else:
				format_decl.override_type = "int"

			format_decl.last_const_val = const_val

	paren_idx = find_main_paren(decl)
	before_paren_stripped = decl[:paren_idx].strip() if paren_idx != -1 else decl

	class_basename = ns_path.split("::")[-1] if ns_path else ""

	is_constructor = before_paren_stripped == class_basename
	is_destructor = before_paren_stripped == "~" + class_basename
	is_operator = "operator" in before_paren_stripped
	has_return_type = " " in before_paren_stripped or "*" in before_paren_stripped or "&" in before_paren_stripped

	if not is_constructor and not is_destructor and not has_return_type:
		base_func_name = before_paren_stripped.split("<")[0]
		bool_prefixes = ("is", "_is", "contains", "_contains", "includes", "_includes", "has", "_has", "can", "_can", "should", "_should", "was", "_was")
		voidptr_prefixes = ("get", "_get")

		if getattr(format_decl, "override_type", None):
			decl = format_decl.override_type + " " + decl
		elif is_operator:
			if any(op in before_paren_stripped for op in ["operator==", "operator<", "operator>", "operator<=", "operator>=", "operator!="]):
				decl = "bool " + decl
		elif matches_prefix(base_func_name, voidptr_prefixes):
			decl = "void* " + decl
		elif matches_prefix(base_func_name, bool_prefixes):
			decl = "bool " + decl
		else:
			decl = "void " + decl
	elif getattr(format_decl, "override_type", None) and has_return_type:
		if return_type.strip() in ("void", "void*"):
			decl = format_decl.override_type + decl[len(return_type):]

	if is_virtual:
		decl = "virtual " + decl

	if not decl.endswith(";") and not decl.endswith("}"):
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
			if next_char.isupper() or next_char == "_" or next_char.isdigit():
				return True
	return False

def load_constants(arch):
	if not arch:
		return {}

	const_file = f"lib{arch}-constants.json"
	if os.path.exists(const_file):
		with open(const_file, "r", encoding="utf-8") as f:
			return json.load(f)

	source_dir = arch
	if not os.path.exists(source_dir):
		print(f"Warning: Source directory {source_dir!r} not found. Constants will not be extracted.")
		return {}

	print(f"Extracting constants from {source_dir!r}...")
	constants = {}
	pattern = re.compile(
		r"^[a-zA-Z0-9_ *&]+?\s+__(?:fastcall|cdecl|stdcall)\s+([a-zA-Z0-9_:]+(?:<[^>]+>)?)\s*\([^)]*\)\n"
		r"\{\n"
		r"\s*return\s+([-+]?[0-9]*\.?[0-9]+|0x[0-9a-fA-F]+(?:LL|L|U|ULL)?|true|false|nullptr|NULL);\n"
		r"\}",
		re.MULTILINE
	)

	c_files = glob.glob(os.path.join(source_dir, "*.c"))
	for c_file in c_files:
		with open(c_file, "r", encoding="utf-8", errors="ignore") as f:
			for match in pattern.finditer(f.read()):
				full_name = match.group(1)
				val = match.group(2)
				if full_name in constants and constants[full_name] != val:
					constants[full_name] = None
				else:
					constants[full_name] = val

	final_constants = {k: v for k, v in constants.items() if v is not None}
	with open(const_file, "w", encoding="utf-8") as f:
		json.dump(final_constants, f, indent=2)
	return final_constants



def get_sort_key(mangled, demangled, class_name):
	if any(x in demangled for x in ["guard variable", "vtable for", "VTT for", "typeinfo"]):
		return (1, "", "", demangled)
	if "_ZZ" in mangled or "_ZGVZ" in mangled:
		return (1, "", "", demangled)

	paren_idx = find_main_paren(demangled)
	if paren_idx == -1:
		return (2, "", "", demangled)

	base = strip_return_type(demangled[:paren_idx])
	parts = split_namespace(base)
	base_func_name = parts[-1].split("<")[0]
	class_basename = class_name.split("::")[-1] if class_name else ""

	if base_func_name == class_basename:
		return (3, "", "", demangled)

	if base_func_name == "~" + class_basename:
		return (4, "", "", demangled)

	bool_prefs = ("is", "_is", "contains", "_contains", "includes", "_includes", "has", "_has", "can", "_can", "should", "_should", "was", "_was")
	if matches_prefix(base_func_name, bool_prefs):
		prop = base_func_name
		for p in bool_prefs:
			if base_func_name.startswith(p):
				prop = base_func_name[len(p):].lstrip("_")
				break
		return (5, prop, base_func_name, demangled)

	getset_prefs = ("get", "_get", "set", "_set")
	if matches_prefix(base_func_name, getset_prefs):
		prop = base_func_name
		for p in getset_prefs:
			if base_func_name.startswith(p):
				prop = base_func_name[len(p):].lstrip("_")
				break
		return (6, prop, base_func_name, demangled)

	if base_func_name.startswith("operator"):
		return (8, base_func_name, base_func_name, demangled)

	return (7, base_func_name, base_func_name, demangled)

def clean_type_names(name):
	name = name.replace("std::__ndk1::basic_string<char, std::__ndk1::char_traits<char>, std::__ndk1::allocator<char> >", "stl_string")
	name = name.replace("std::__ndk1::basic_string<char, std::__ndk1::char_traits<char>, std::__ndk1::allocator<char>>", "stl_string")
	name = re.sub(r"std::__ndk1::vector<(.*?),\s*std::__ndk1::allocator<\1\s*>\s*>", r"stl_vector<\1>", name)
	name = re.sub(r"std::__ndk1::unique_ptr<(.*?),\s*std::__ndk1::default_delete<\1\s*>\s*>", r"stl_unique_ptr<\1>", name)
	name = name.replace("std::__ndk1::", "stl_")
	return name

def parse_vtables(filepath):
	vtables = {}
	current_vtable = None
	with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
		for line in f:
			line = line.strip()
			if line.startswith("# _ZTV"):
				current_vtable = line[6:]
				vtables[current_vtable] = []
			elif line.startswith("|") and current_vtable:
				parts = [p.strip() for p in line.split("|")]
				if len(parts) >= 4 and parts[1].isdigit():
					idx = int(parts[1])
					method = parts[2].strip("` ")
					while len(vtables[current_vtable]) <= idx:
						vtables[current_vtable].append(None)
					vtables[current_vtable][idx] = method
	return vtables

def extract_class_from_mangled(mangled):
	if not mangled or mangled == "__cxa_pure_virtual": return None
	if mangled.startswith("_ZNK"): content = mangled[4:]
	elif mangled.startswith("_ZN"): content = mangled[3:]
	elif mangled.startswith("_ZTV"): content = mangled[4:]
	else: return None

	parts = []
	while content:
		if content.startswith("D0") or content.startswith("D1") or content.startswith("D2") or content.startswith("C1") or content.startswith("C2"):
			parts.append(content[:2])
			break
		m = re.match(r"^(\d+)", content)
		if not m: break
		length = int(m.group(1))
		part_len = len(m.group(1)) + length
		part = content[:part_len]
		parts.append(part)
		content = content[part_len:]

	if not parts: return None
	if len(parts) > 1:
		class_parts = parts[:-1]
		if len(class_parts) > 1: return "N" + "".join(class_parts) + "E"
		return class_parts[0]
	return parts[0]

def resolve_pure_virtuals(vtables, method_index, children_map):
	resolved = defaultdict(dict)
	for v1_name, v1_slots in vtables.items():
		for idx, m1 in enumerate(v1_slots):
			if m1 == "__cxa_pure_virtual":
				related_v_counts = defaultdict(int)
				for i, method_in_v1 in enumerate(v1_slots):
					if i == idx: continue
					if not method_in_v1 or method_in_v1 == "__cxa_pure_virtual": continue
					if "D0Ev" in method_in_v1 or "D2Ev" in method_in_v1: continue
					for related_v in method_index[i].get(method_in_v1, []):
						if related_v != v1_name:
							related_v_counts[related_v] += 1
				for child_v in children_map.get(v1_name, []):
					related_v_counts[child_v] += 5
				candidates = []
				for related_v, count in related_v_counts.items():
					if len(vtables[related_v]) > idx:
						m2 = vtables[related_v][idx]
						if m2 and m2 != "__cxa_pure_virtual":
							candidates.append((count, m2))
				if candidates:
					candidates.sort(reverse=True, key=lambda x: x[0])
					resolved[v1_name][idx] = candidates[0][1]
	return resolved

class ClassData:
	def __init__(self):
		self.v_name = None
		self.parents = []
		self.heuristic_parents = set()
		self.slots = []
		self.syms = []
		self.is_dummy_enum = False

def generate_headers():
	global CONSTANT_METHODS

	if len(sys.argv) > 1:
		arch = sys.argv[1]
		input_syms = f"lib{arch}-symbols.txt"
		input_vtables = f"lib{arch}-vtable.md"
		output_dir = f"{arch}-headers"
	else:
		arch = ""
		input_syms = "symbols.txt"
		input_vtables = "vtable.md"
		output_dir = "headers"

	CONSTANT_METHODS = load_constants(arch)
	if CONSTANT_METHODS:
		print(f"Loaded {len(CONSTANT_METHODS)} constants.")

	if not os.path.exists(input_syms):
		print(f"Error: Symbols file {input_syms!r} not found.")
		return

	vtables = {}
	v_info = {}
	direct_parents = {}
	heuristic_links = set()
	resolved_pures = {}
	has_vtables = False

	if os.path.exists(input_vtables):
		print(f"Parsing vtables from {input_vtables!r}...")
		has_vtables = True
		vtables = parse_vtables(input_vtables)

		for v_name in list(vtables.keys()):
			try:
				dummy_mangled = f"_Z1fP{v_name}"
				demangled_dummy = cpp_demangle.demangle(dummy_mangled)
				if demangled_dummy.startswith("f(") and demangled_dummy.endswith("*)"):
					class_name = demangled_dummy[2:-2]
				else:
					class_name = v_name
			except Exception:
				class_name = v_name

			class_str = class_name
			parts = split_namespace(class_str)
			if len(parts) > 1:
				file_name = re.sub(r"[^A-Za-z0-9_~]", "", parts[0].split("<")[0])
				if "<" in parts[0]:
					class_name = "::".join([parts[0]] + parts[1:])
				else:
					class_name = "::".join(parts[1:])
			else:
				file_name = re.sub(r"[^A-Za-z0-9_~]", "", class_str.split("<")[0])
				class_name = ""

			if not file_name: file_name = "global"
			v_info[v_name] = {"file": file_name, "class": class_name, "full_class": class_str}

		print("Building inheritance tree...")
		ancestors = defaultdict(set)
		method_index = defaultdict(lambda: defaultdict(list))
		for v_name, slots in vtables.items():
			for idx, m in enumerate(slots):
				if m and m != "__cxa_pure_virtual":
					method_index[idx][m].append(v_name)
				cls = extract_class_from_mangled(m)
				is_dtor = m and ("D0" in m or "D1" in m or "D2" in m)
				if cls and cls != v_name and not is_dtor:
					if len(vtables.get(cls, [])) <= len(slots):
						ancestors[v_name].add(cls)

		name_to_v_name = {info["full_class"]: v_name for v_name, info in v_info.items() if info["full_class"]}

		for v_name, slots in vtables.items():
			if not ancestors.get(v_name):
				c_name = v_info[v_name]["full_class"]
				if not c_name: continue
				best_p_name, best_p_len = None, -1
				for i in range(len(c_name)):
					suffix = c_name[i:]
					if suffix in name_to_v_name and len(suffix) > 3 and suffix != c_name:
						p_v_name = name_to_v_name[suffix]
						if len(vtables.get(p_v_name, [])) <= len(slots):
							if len(suffix) > best_p_len:
								best_p_len = len(suffix)
								best_p_name = p_v_name
				if best_p_name:
					ancestors[v_name].add(best_p_name)
					method_index[-1][best_p_name].append(v_name)
					heuristic_links.add((v_name, best_p_name))

		for cls, ancs in ancestors.items():
			parents = set(ancs)
			redundant = set()
			for p1 in parents:
				stack = [p1]
				visited = set()
				while stack:
					curr = stack.pop()
					if curr in visited: continue
					visited.add(curr)
					for p in ancestors.get(curr, []):
						redundant.add(p)
						stack.append(p)
			direct_parents[cls] = list(parents - redundant)

		children_map = defaultdict(list)
		for child_v, parents in direct_parents.items():
			for p in parents:
				children_map[p].append(child_v)

		print("Resolving pure virtual methods...")
		resolved_pures = resolve_pure_virtuals(vtables, method_index, children_map)
	else:
		print(f"Warning: VTable dump {input_vtables!r} not found. Generating without virtual modifiers and inheritance.")

	print(f"Reading symbols from {input_syms!r}...")
	file_map = defaultdict(lambda: defaultdict(ClassData))
	file_needs_stl = {}

	with open(input_syms, "r", encoding="utf-8") as f:
		for line in f:
			mangled = line.strip()
			if not mangled: continue
			try:
				demangled = cpp_demangle.demangle(mangled)
			except Exception:
				demangled = mangled

			orig_file_name, _ = parse_demangled(demangled, mangled)
			if orig_file_name in ("std", "__cxxabiv1", "__gnu_cxx"): continue

			demangled = clean_type_names(demangled)
			file_name, class_name = parse_demangled(demangled, mangled)
			if not file_name: file_name = "global"

			file_map[file_name][class_name].syms.append((mangled, demangled))
			if "stl_" in demangled: file_needs_stl[file_name] = True

	if has_vtables:
		for v_name, slots in vtables.items():
			file_name = v_info[v_name]["file"]
			class_name = v_info[v_name]["class"]
			if file_name in ("std", "__cxxabiv1", "__gnu_cxx"): continue
			if "_ptr" in v_name or re.match(r"^\d", class_name): continue

			is_valid = False
			for m in slots:
				if m and m != "__cxa_pure_virtual" and "D0Ev" not in m and "D2Ev" not in m:
					if extract_class_from_mangled(m) == v_name:
						is_valid = True
						break
			if not is_valid:
				parents = direct_parents.get(v_name, [])
				if not parents:
					if len(slots) > 2: is_valid = True
				else:
					max_p_len = max(len(vtables.get(p, [])) for p in parents)
					if len(slots) > max_p_len: is_valid = True

			if is_valid:
				cdata = file_map[file_name][class_name]
				cdata.v_name = v_name
				cdata.slots = slots
				cdata.parents = direct_parents.get(v_name, [])
				for p in cdata.parents:
					if (v_name, p) in heuristic_links:
						cdata.heuristic_parents.add(p)

	if os.path.exists(output_dir):
		bak_dir = output_dir + ".bak"
		if os.path.exists(bak_dir): shutil.rmtree(bak_dir, ignore_errors=True)
		try: os.rename(output_dir, bak_dir)
		except Exception: pass
	os.makedirs(output_dir, exist_ok=True)

	print(f"Found {len(file_map)} files to generate.")

	for file_name, classes in list(file_map.items()):
		for class_name, cdata in list(classes.items()):
			known_last_parts = set()
			for m, d in cdata.syms:
				parts_d = d.split("::")
				if parts_d:
					known_last_parts.add(parts_d[-1])
			for mangled, demangled in cdata.syms:
				for match in re.finditer(r"\b(?:[A-Za-z0-9_]+::)+[A-Z][a-zA-Z0-9_]*\b", demangled):
					if match.end() < len(demangled) and demangled[match.end()] == "(": continue
					cls = match.group(0)
					parts = cls.split("::")
					last_part = parts[-1] if parts else cls

					if last_part in known_last_parts: continue
					if len(parts) >= 2 and parts[-1] == parts[-2]: continue
					if parts[0] in file_map:
						rel_cls = "::".join(parts[1:])
						if rel_cls and rel_cls not in file_map[parts[0]]:
							file_map[parts[0]][rel_cls].is_dummy_enum = True

	print(f"Generating headers in {output_dir!r}...")

	known_classes = set(file_map.keys())

	for file_name, classes in file_map.items():
		if "anonymous namespace" in file_name or "__func" in file_name or "__cxx" in file_name or "__ndk1" in file_name:
			continue
		safe_file_name = "".join(c for c in file_name if c.isalnum() or c == "_")[:64]
		if not safe_file_name: safe_file_name = "global"

		header_path = os.path.join(output_dir, f"{safe_file_name}.h")
		includes = set()

		forward_declares = set()
		for class_name, cdata in classes.items():
			for p in cdata.parents:
				if p in v_info:
					p_file = v_info[p]["file"]
					if p_file != file_name:
						safe_p_file = "".join(c for c in p_file if c.isalnum() or c == "_")[:64]
						includes.add(f"{safe_p_file}.h")

			output_slots = []
			if cdata.slots:
				v_name = cdata.v_name
				for idx, mangled in enumerate(cdata.slots):
					if not mangled: continue
					if mangled == "__cxa_pure_virtual":
						if v_name in resolved_pures and idx in resolved_pures[v_name]:
							output_slots.append(resolved_pures[v_name][idx])
						continue
					if "D0Ev" in mangled or "D2Ev" in mangled:
						output_slots.append(mangled)
						continue
					m_class = extract_class_from_mangled(mangled)
					if m_class == v_name:
						output_slots.append(mangled)

			for mangled in output_slots:
				if "D0Ev" in mangled or "D1Ev" in mangled or "D2Ev" in mangled:
					continue
				try:
					dem = cpp_demangle.demangle(mangled)
					if "std::" in dem or "__ndk1" in dem:
						file_needs_stl[file_name] = True
					for match in re.finditer(r"\b(?:[A-Za-z0-9_]+::)*[A-Z][a-zA-Z0-9_]*\b", dem):
						cls = match.group(0)
						if cls == file_name or cls == safe_file_name or cls.startswith(safe_file_name + "::") or cls.startswith(file_name + "::"):
							continue
						if "::" in cls:
							parts = cls.split("::")
							if parts[0] in known_classes:
								if f"{parts[0]}.h" not in includes and parts[0] != safe_file_name:
									includes.add(f"{parts[0]}.h")
							else:
								decl = ""
								for p in parts[:-1]: decl += f"namespace {p} {{ "
								decl += f"class {parts[-1]}; "
								for p in parts[:-1]: decl += "}"
								forward_declares.add(decl)
						else:
							if f"{cls}.h" not in includes:
								forward_declares.add(f"class {cls};")
				except: pass

			for mangled, demangled in cdata.syms:
				for match in re.finditer(r"\b(?:[A-Za-z0-9_]+::)*[A-Z][a-zA-Z0-9_]*\b", demangled):
					cls = match.group(0)
					if cls == file_name or cls == safe_file_name or cls.startswith(safe_file_name + "::") or cls.startswith(file_name + "::"):
						continue
					if "::" in cls:
						parts = cls.split("::")
						if parts[0] in known_classes:
							if f"{parts[0]}.h" not in includes and parts[0] != safe_file_name:
								includes.add(f"{parts[0]}.h")
						else:
							decl = ""
							for p in parts[:-1]: decl += f"namespace {p} {{ "
							decl += f"class {parts[-1]}; "
							for p in parts[:-1]: decl += "}"
							forward_declares.add(decl)
					else:
						if f"{cls}.h" not in includes:
							forward_declares.add(f"class {cls};")

		with open(header_path, "w", encoding="utf-8") as f:
			f.write("#pragma once\n\n")
			has_stl = file_needs_stl.get(file_name, False) or file_needs_stl.get(safe_file_name, False)
			if has_stl: f.write("#include <stl.h>\n")
			for inc in sorted(list(includes)):
				f.write(f"#include \"{inc}\"\n")
			if includes or has_stl: f.write("\n")

			if forward_declares:
				for decl in sorted(list(forward_declares)):
					if decl.startswith("namespace") or decl.startswith("class"):
						f.write(f"{decl}\n")
					else:
						f.write(f"class {decl};\n")
				f.write("\n")

			if safe_file_name == "global":
				for class_name, cdata in classes.items():
					cdata.syms.sort(key=lambda x: get_sort_key(x[0], x[1], ""))
					for mangled, demangled in cdata.syms:
						f_decl_str = format_decl("", demangled, mangled, "")
						if getattr(format_decl, "last_const_val", None):
							f_decl_str += f" = {format_decl.last_const_val}"
						f.write(f_decl_str + "\n")
				continue

			has_nested = any(c for c in classes.keys())
			is_class = not has_nested

			for mangled, demangled in classes.get("", ClassData()).syms:
				if any(x in demangled for x in ["typeinfo", "vtable", "VTT"]):
					is_class = True; break
				category = get_sort_key(mangled, demangled, safe_file_name)[0]
				if category in (3, 4):
					is_class = True; break

			if classes.get("", ClassData()).v_name is not None:
				is_class = True

			if not is_class:
				f.write(f"namespace {safe_file_name} {{\n")
				indent = "\t"
			else:
				cdata = classes.get("", ClassData())
				inheritance_str = ""
				if cdata and cdata.parents:
					parent_names = []
					for p in cdata.parents:
						if p in v_info:
							mark = " /* inaccurate */" if p in cdata.heuristic_parents else ""
							p_full_class = v_info[p]["full_class"]
							parent_names.append(f"public {p_full_class}{mark}")
					if parent_names: inheritance_str = " : " + ", ".join(parent_names)
				f.write(f"class {safe_file_name}{inheritance_str} {{\npublic:\n")
				indent = "\t"

			tree = {"__cdata__": None, "__sub__": {}}
			for class_name, cdata in classes.items():
				current = tree
				if class_name:
					parts = split_namespace(class_name)
					for p in parts:
						if p not in current["__sub__"]:
							current["__sub__"][p] = {"__cdata__": None, "__sub__": {}}
						current = current["__sub__"][p]
				current["__cdata__"] = cdata



			def write_node(node, current_indent, basename, full_ns_path):
				cdata = node["__cdata__"]

				if basename:
					if cdata and getattr(cdata, "is_dummy_enum", False):
						f.write(f"{current_indent}enum class {basename} : int;\n")
						return

					inheritance_str = ""
					if cdata and cdata.parents:
						parent_names = []
						for p in cdata.parents:
							if p in v_info:
								mark = " /* inaccurate */" if p in cdata.heuristic_parents else ""
								p_full_class = v_info[p]["full_class"]
								parent_names.append(f"public {p_full_class}{mark}")
						if parent_names: inheritance_str = " : " + ", ".join(parent_names)

					if "<" in basename: f.write(f"{current_indent}template<>\n")
					f.write(f"{current_indent}class {basename}{inheritance_str} {{\n{current_indent}public:\n")
					inner_indent = current_indent + "\t"
				else:
					inner_indent = current_indent

				has_content = False
				if cdata:
					cdata.syms.sort(key=lambda x: get_sort_key(x[0], x[1], full_ns_path))
					emitted_virtual_mangled = set()
					virtual_lines = []
					destructors_emitted = False

					if cdata.v_name:
						v_name = cdata.v_name
						class_name = v_info[v_name]["class"]
						for idx, mangled in enumerate(cdata.slots):
							if not mangled: continue
							if "D0Ev" in mangled or "D2Ev" in mangled:
								emitted_virtual_mangled.add(mangled)
								if not destructors_emitted:
									virtual_lines.append(f"{inner_indent}virtual ~{basename if basename else safe_file_name}(); // slot {idx}: {mangled}")
									destructors_emitted = True
								continue
							if mangled == "__cxa_pure_virtual":
								if idx in resolved_pures.get(v_name, {}):
									best_m2 = resolved_pures[v_name][idx]
									try:
										dem = cpp_demangle.demangle(best_m2)
										dem = clean_type_names(dem)
										decl = format_decl(class_name, dem, best_m2, "", is_virtual=True)
										idx_comment = decl.find("//")
										before_comment = decl[:idx_comment].rstrip() if idx_comment != -1 else decl.rstrip()
										if before_comment.endswith(";") and not before_comment.endswith("};"): before_comment = before_comment[:-1] + " = 0;"
										if not before_comment.endswith(";") and not before_comment.endswith("}"): before_comment += ";"
										const_str = f" = {format_decl.last_const_val}" if getattr(format_decl, "last_const_val", None) else ""
										virtual_lines.append(f"{inner_indent}{before_comment.strip()} // slot {idx}: {best_m2}{const_str}")
									except:
										virtual_lines.append(f"{inner_indent}virtual void unk_vtable_slot_{idx}() = 0; // slot {idx}: __cxa_pure_virtual")
								else:
									virtual_lines.append(f"{inner_indent}virtual void unk_vtable_slot_{idx}() = 0; // slot {idx}: __cxa_pure_virtual")
								continue

							m_class = extract_class_from_mangled(mangled)
							if m_class == v_name:
								emitted_virtual_mangled.add(mangled)
								try:
									dem = cpp_demangle.demangle(mangled)
									dem = clean_type_names(dem)
									decl = format_decl(class_name, dem, mangled, "", is_virtual=True)
									idx_comment = decl.find("//")
									before_comment = decl[:idx_comment].rstrip() if idx_comment != -1 else decl.rstrip()
									if not before_comment.endswith(";") and not before_comment.endswith("}"): before_comment += ";"
									const_str = f" = {format_decl.last_const_val}" if getattr(format_decl, "last_const_val", None) else ""
									virtual_lines.append(f"{inner_indent}{before_comment.strip()} // slot {idx}: {mangled}{const_str}")
								except:
									virtual_lines.append(f"{inner_indent}// virtual parse_error // slot {idx}: {mangled}")

					fields_lines = []
					method_lines = []
					for mangled, demangled in cdata.syms:
						if mangled in emitted_virtual_mangled: continue

						if "D0Ev" in mangled or "D2Ev" in mangled or ("~" in demangled and "::~" in demangled):
							if destructors_emitted: continue
							destructors_emitted = True

						paren_idx = find_main_paren(demangled)
						decl_str = format_decl(full_ns_path, demangled, mangled, inner_indent)
						if getattr(format_decl, "last_const_val", None):
							decl_str += f" = {format_decl.last_const_val}"

						if paren_idx == -1 and "guard variable" not in demangled and "_ZZ" not in mangled and "_ZGVZ" not in mangled:
							fields_lines.append(decl_str)
						else:
							method_lines.append(decl_str)

					for line in fields_lines: f.write(f"{line}\n")
					if fields_lines and (virtual_lines or method_lines): f.write("\n")

					for line in virtual_lines: f.write(f"{line}\n")
					if virtual_lines and method_lines: f.write("\n")

					for line in method_lines: f.write(f"{line}\n")

					has_content = bool(fields_lines or virtual_lines or method_lines)

				first_sub = True
				for sub_name, sub_node in node["__sub__"].items():
					next_ns = full_ns_path + "::" + sub_name if full_ns_path else sub_name
					need_sep = not first_sub or (first_sub and has_content)
					if need_sep: f.write("\n")
					first_sub = False
					write_node(sub_node, inner_indent, sub_name, next_ns)

				if basename: f.write(f"{current_indent}}};\n")

			write_node(tree, indent, "", file_name)

			if not is_class: f.write("}\n")
			else: f.write("};\n")

	print("Header generation completed.")

if __name__ == "__main__":
	generate_headers()
