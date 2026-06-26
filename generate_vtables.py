import os
import re
import shutil
import sys
import cpp_demangle
from collections import defaultdict
from generate_headers import parse_demangled, split_namespace, format_decl

def parse_vtables(filepath):
	vtables = {}
	current_vtable = None
	with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
		for line in f:
			line = line.strip()
			if line.startswith('# _ZTV'):
				current_vtable = line[6:]
				vtables[current_vtable] = []
			elif line.startswith('|') and current_vtable:
				parts = [p.strip() for p in line.split('|')]
				if len(parts) >= 4 and parts[1].isdigit():
					idx = int(parts[1])
					method = parts[2].strip('` ')
					while len(vtables[current_vtable]) <= idx:
						vtables[current_vtable].append(None)
					vtables[current_vtable][idx] = method
	return vtables

def extract_class_from_mangled(mangled):
	if not mangled or mangled == '__cxa_pure_virtual': return None
	if mangled.startswith('_ZNK'): start = 4
	elif mangled.startswith('_ZN'): start = 3
	else: return None
	m = re.match(r'^(\d+)', mangled[start:])
	if not m: return None
	length = int(m.group(1))
	return m.group(1) + mangled[start+len(m.group(1)):start+len(m.group(1))+length]

def resolve_pure_virtuals(vtables, method_index, children_map):
	resolved = defaultdict(dict)
	for v1_name, v1_slots in vtables.items():
		for idx, m1 in enumerate(v1_slots):
			if m1 == '__cxa_pure_virtual':
				related_v_counts = defaultdict(int)
				for i, method_in_v1 in enumerate(v1_slots):
					if i == idx: continue
					if not method_in_v1 or method_in_v1 == '__cxa_pure_virtual': continue
					if 'D0Ev' in method_in_v1 or 'D2Ev' in method_in_v1: continue
					for related_v in method_index[i].get(method_in_v1, []):
						if related_v != v1_name:
							related_v_counts[related_v] += 1
				for child_v in children_map.get(v1_name, []):
					related_v_counts[child_v] += 5
				candidates = []
				for related_v, count in related_v_counts.items():
					if len(vtables[related_v]) > idx:
						m2 = vtables[related_v][idx]
						if m2 and m2 != '__cxa_pure_virtual':
							candidates.append((count, m2))
				if candidates:
					candidates.sort(reverse=True, key=lambda x: x[0])
					resolved[v1_name][idx] = candidates[0][1]
	return resolved

def main():
	if len(sys.argv) > 1:
		arch = sys.argv[1]
		input_file = f"lib{arch}-vtable.md"
		output_dir = f"{arch}-vtables"
	else:
		input_file = "minecraftpe.md"
		output_dir = "vtables"

	if not os.path.exists(input_file):
		print(f"Error: {input_file} not found.")
		return

	print(f"Parsing vtables from {input_file}...")
	vtables = parse_vtables(input_file)

	v_info = {}
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

		parts = split_namespace(class_name)
		file_name = parts[0] if parts else class_name
		file_name = re.sub(r'[^A-Za-z0-9_~]', '', file_name.split('<')[0])
		if not file_name: file_name = "global"
		v_info[v_name] = {'file': file_name, 'class': class_name}

	print("Building inheritance tree...")
	ancestors = defaultdict(set)
	method_index = defaultdict(lambda: defaultdict(list))
	for v_name, slots in vtables.items():
		for idx, m in enumerate(slots):
			if m and m != '__cxa_pure_virtual':
				method_index[idx][m].append(v_name)
			cls = extract_class_from_mangled(m)
			if cls and cls != v_name:
				ancestors[v_name].add(cls)

	direct_parents = {}
	for cls, ancs in ancestors.items():
		parents = set(ancs)
		for a in ancs:
			if a in ancestors:
				for a_anc in ancestors[a]:
					if a_anc in parents:
						parents.remove(a_anc)
		direct_parents[cls] = list(parents)

	name_to_v_name = {}
	for v_name, info in v_info.items():
		if info['class']: name_to_v_name[info['class']] = v_name

	heuristic_links = set()
	for v_name, slots in vtables.items():
		if not direct_parents.get(v_name):
			c_name = v_info[v_name]['class']
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
				direct_parents[v_name] = [best_p_name]
				method_index[-1][best_p_name].append(v_name)
				heuristic_links.add((v_name, best_p_name))

	children_map = defaultdict(list)
	for child_v, parents in direct_parents.items():
		for p in parents:
			children_map[p].append(child_v)

	print("Resolving pure virtual methods...")
	resolved_pures = resolve_pure_virtuals(vtables, method_index, children_map)

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

	file_map = defaultdict(list)
	for v_name in list(vtables.keys()):
		file_name = v_info[v_name]['file']
		class_name = v_info[v_name]['class']
		if file_name in ('std', '__cxxabiv1', '__gnu_cxx'): continue
		if '_ptr' in v_name or re.match(r'^\d', class_name): continue

		is_valid = False
		slots = vtables.get(v_name, [])
		for m in slots:
			if m and m != '__cxa_pure_virtual' and 'D0Ev' not in m and 'D2Ev' not in m:
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
		if not is_valid: continue
		file_map[file_name].append(v_name)

	print(f"Generating headers in '{output_dir}'...")
	for file_name, v_names in file_map.items():
		safe_file_name = "".join(c for c in file_name if c.isalnum() or c == '_')[:64]
		if not safe_file_name: safe_file_name = "global"
		includes = set()
		for v_name in v_names:
			for p in direct_parents.get(v_name, []):
				if p in v_info:
					p_file = v_info[p]['file']
					if p_file != file_name:
						safe_p_file = "".join(c for c in p_file if c.isalnum() or c == '_')[:64]
						includes.add(f'{safe_p_file}.h')

		header_path = os.path.join(output_dir, f"{safe_file_name}.h")
		with open(header_path, 'w', encoding='utf-8') as f:
			f.write("#pragma once\n\n")
			for inc in sorted(list(includes)):
				f.write(f'#include "{inc}"\n')
			if includes: f.write("\n")

			tree = {'__vname__': None, '__sub__': {}}
			for v_name in v_names:
				class_name = v_info[v_name]['class']
				current = tree
				if class_name:
					parts = split_namespace(class_name)
					for p in parts:
						if p not in current['__sub__']:
							current['__sub__'][p] = {'__vname__': None, '__sub__': {}}
						current = current['__sub__'][p]
				current['__vname__'] = v_name

			def write_node(node, current_indent, basename):
				v_name = node['__vname__']
				if basename:
					inheritance_str = ""
					if v_name and v_name in direct_parents:
						parents = direct_parents[v_name]
						parent_names = []
						for p in parents:
							if p in v_info:
								mark = " /* inaccurate */" if (v_name, p) in heuristic_links else ""
								parent_names.append(f"public {v_info[p]['class']}{mark}")
						if parent_names: inheritance_str = " : " + ", ".join(parent_names)
					f.write(f"{current_indent}class {basename}{inheritance_str} {{\n{current_indent}public:\n")

				if v_name:
					slots = vtables.get(v_name, [])
					destructors_emitted = False
					class_name = v_info[v_name]['class']
					for idx, mangled in enumerate(slots):
						if not mangled: continue
						if 'D0Ev' in mangled or 'D2Ev' in mangled:
							if not destructors_emitted:
								f.write(f"{current_indent}\tvirtual ~{basename if basename else class_name}();\n")
								destructors_emitted = True
							continue
						if mangled == '__cxa_pure_virtual':
							if idx in resolved_pures.get(v_name, {}):
								best_m2 = resolved_pures[v_name][idx]
								try:
									dem = cpp_demangle.demangle(best_m2)
									decl = format_decl(class_name, dem, best_m2, "")
									idx_comment = decl.find('//')
									before_comment = decl[:idx_comment].rstrip() if idx_comment != -1 else decl.rstrip()
									if before_comment.endswith(';'): before_comment = before_comment[:-1] + ' = 0;'
									if not before_comment.endswith(';'): before_comment += ';'
									f.write(f"{current_indent}\tvirtual {before_comment.strip()} // slot {idx}\n")
								except:
									f.write(f"{current_indent}\tvirtual void unk_vtable_slot_{idx}() = 0;\n")
							else:
								f.write(f"{current_indent}\tvirtual void unk_vtable_slot_{idx}() = 0;\n")
							continue
						m_class = extract_class_from_mangled(mangled)
						if m_class == v_name:
							try:
								dem = cpp_demangle.demangle(mangled)
								decl = format_decl(class_name, dem, mangled, "")
								idx_comment = decl.find('//')
								before_comment = decl[:idx_comment].rstrip() if idx_comment != -1 else decl.rstrip()
								if not before_comment.endswith(';'): before_comment += ';'
								f.write(f"{current_indent}\tvirtual {before_comment.strip()} // slot {idx}\n")
							except:
								f.write(f"{current_indent}\t// virtual parse_error // slot {idx} // {mangled}\n")

				for sub_name, sub_node in node['__sub__'].items():
					write_node(sub_node, current_indent + "\t" if basename else current_indent, sub_name)
				if basename: f.write(f"{current_indent}}};\n")

			for sub_name, sub_node in tree['__sub__'].items():
				write_node(sub_node, "", sub_name)

if __name__ == '__main__':
	main()
