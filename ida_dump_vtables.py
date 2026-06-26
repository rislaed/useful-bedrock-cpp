import idaapi, idautils, idc, ida_ida, ida_kernwin

def is_in_exec_segment(ea):
	# Clear Thumb-bit (LSB) for ARM32
	ea = ea & ~1
	seg = idaapi.getseg(ea)
	if not seg:
		return False
	return (seg.perm & idaapi.SEGPERM_EXEC) != 0

def request_dump_vtables():
	is_64 = ida_ida.inf_get_app_bitness() == 64
	ptr_size = 8 if is_64 else 4

	output_name = ida_kernwin.ask_file(1, "*.md", "Save vtables as")
	if not output_name:
		print("Vtable dumping cancelled.")
		return

	print(f"Starting vtable dump to {output_name}...")

	count = 0
	with open(output_name, "w", encoding="utf-8") as f:
		for ea, name in idautils.Names():
			if name.startswith("_ZTV") or name.startswith("._ZTV"):
				clean_name = name if name.startswith("_ZTV") else name[1:]
				f.write(f"# {clean_name}\n")
				f.write("| | |\n")
				f.write("|---|---|\n")

				curr_ea = ea + (2 * ptr_size)
				slot = 0

				while True:
					if is_64:
						func_ea = idc.get_qword(curr_ea)
					else:
						func_ea = idc.get_wide_dword(curr_ea)

					if func_ea == 0 or not is_in_exec_segment(func_ea):
						break

					if slot > 0:
						curr_name = idc.get_name(curr_ea, idc.GN_VISIBLE)
						if curr_name and curr_name.startswith("_ZTV"):
							break

					func_name = idc.get_name(func_ea, idc.GN_VISIBLE)
					if not func_name:
						func_name = f"sub_{func_ea:X}"

					f.write(f"| {slot} | `{func_name}` |\n")

					curr_ea += ptr_size
					slot += 1

				count += 1

	print(f"Vtable dump finished! Dumped {count} vtables.")

if __name__ == "__main__":
	request_dump_vtables()
