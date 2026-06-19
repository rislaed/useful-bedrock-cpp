import idaapi, idautils, ida_funcs, ida_hexrays, ida_lines, ida_ida, ida_nalt, ida_kernwin
import os
import time


def resolve_checkpoint(file):
	if not os.path.exists(file):
		return 0

	with open(file, "r") as f:
		content = f.read().strip()

	if not content:
		raise ValueError("Checkpoint file exists, but could not be empty!")
	if content.isdigit():
		return int(content)

	try:
		addr = int(content, 16)
		func = ida_funcs.get_func(addr)
		if func:
			print(f"Checkpoint {hex(addr)} resolved, address starts at {hex(func.start_ea)}.")
			funcs = list(idautils.Functions())
			return funcs.index(func.start_ea)
		else:
			raise ValueError(f"Checkpoint {content!r} could not be resolved from address!")
	except ValueError:
		raise ValueError(f"Checkpoint {content!r} is invalid number!")

def save_checkpoint(file, index):
	with open(file, "w") as f:
		f.write(str(index))

def remove_checkpoint(file):
	if os.path.exists(file):
		os.remove(file)

def format_time(seconds):
	m, s = divmod(int(seconds), 60)
	h, m = divmod(m, 60)
	d, h = divmod(h, 24)
	return f"{d}d {h:2d}h {m:2d}m {s:2d}s"

def main():
	idaapi.auto_wait()
	pad = 16 if ida_ida.inf_get_app_bitness() == 64 else 8
	input_name = ida_nalt.get_root_filename()
	if not input_name:
		input_name = "dumped_code"

	default_path = input_name + ".c"
	output_name = ida_kernwin.ask_file(1, default_path, "C/C++ Source File (*.c)|*.c")
	if not output_name:
		print("Decompilation cancelled.")
		return
	output_checkpoint = output_name + ".index"

	start_idx = resolve_checkpoint(output_checkpoint)
	funcs = list(idautils.Functions())
	total_funcs = len(funcs)
	start_time = time.time()

	print(f"Starting decompilation of {input_name} to {output_name}...")
	print(f"Total functions to process: {start_idx}/{total_funcs}")

	write_mode = "a" if start_idx > 0 else "w"
	with open(output_name, write_mode, encoding="utf-8", buffering=1024 * 1024) as f:
		if start_idx == 0:
			f.write("/*\n")
			f.write(" * ============================================================================\n")
			f.write(" * Copyright (c) 2026 Romi\n")
			f.write(" * \n")
			f.write(" * Permission is hereby granted, free of charge, to any person obtaining a copy\n")
			f.write(" * of this software and associated documentation files (the \"Software\"), to deal\n")
			f.write(" * in the Software without restriction, including without limitation the rights\n")
			f.write(" * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n")
			f.write(" * copies of the Software, and to permit persons to whom the Software is\n")
			f.write(" * furnished to do so, subject to the following conditions:\n")
			f.write(" * \n")
			f.write(" * The above copyright notice and this permission notice shall be included in all\n")
			f.write(" * copies or substantial portions of the Software.\n")
			f.write(" * \n")
			f.write(" * THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n")
			f.write(" * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n")
			f.write(" * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n")
			f.write(" * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n")
			f.write(" * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n")
			f.write(" * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n")
			f.write(" * SOFTWARE.\n")
			f.write(" * ============================================================================\n")
			f.write(" */\n\n")

			f.write("// Function declarations\n\n")
			f.write("// Data declarations\n\n\n")

		successful = start_idx
		for i in range(start_idx, total_funcs):
			ea = funcs[i]
			try:
				cfunc = ida_hexrays.decompile(ea)
				if cfunc:
					f.write(f"//----- ({ea:0{pad}X}) " + "-" * 56 + "\n")
					for line in cfunc.get_pseudocode():
						f.write(ida_lines.tag_remove(line.line) + "\n")
					f.write("\n")
					successful += 1
			except Exception:
				pass

			if (i + 1) % 1000 == 0 or (i + 1) == total_funcs:
				current_idx = i + 1
				if current_idx % 10000 == 0:
					ida_hexrays.clear_cached_cfuncs()

				save_checkpoint(output_checkpoint, current_idx)
				f.flush()

				elapsed = time.time() - start_time
				processed_count = current_idx - start_idx
				if processed_count > 0:
					rate = processed_count / elapsed
					remaining = total_funcs - current_idx
					eta_seconds = remaining / rate
					eta_str = f"| ETA: {format_time(eta_seconds)} "
				else:
					eta_str = ""

				missed = current_idx - successful
				print(f"[{current_idx}/{total_funcs}] {(current_idx / total_funcs)*100:.1f}% {eta_str}| Missed: {missed}")

	remove_checkpoint(output_checkpoint)
	print("Decompilation finished!")

if __name__ == "__main__":
	main()
