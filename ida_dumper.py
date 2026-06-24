import idaapi, idautils, ida_funcs, ida_hexrays, ida_lines, ida_ida, ida_nalt, ida_kernwin
import os
import time
import gc

def resolve_checkpoint(output_name, funcs):
	if not os.path.exists(output_name):
		return 0

	with open(output_name, "rb") as f:
		f.seek(max(0, os.path.getsize(output_name) - 10000))
		data = f.read()

	idx = data.rfind(b"//-----")
	if idx != -1:
		offset = os.path.getsize(output_name) - len(data) + idx
		line_end = data.find(b"\n", idx)
		header = data[idx:line_end].decode("utf-8", errors="ignore")

		try:
			addr_str = header.split("(")[1].split(")")[0]
			addr = int(addr_str, 16)
		except (IndexError, ValueError):
			if ida_kernwin.ask_yn(1, f"Failed to parse address from header:\n{header}\nOverwrite and start from beginning?") != 1:
				return -1
			return 0

		func = ida_funcs.get_func(addr)
		if func:
			try:
				start_idx = funcs.index(func.start_ea)
				with open(output_name, "r+b") as f2:
					f2.truncate(offset)
				print(f"Checkpoint 0x{addr:X} resolved, resuming from index {start_idx}.")
				return start_idx
			except ValueError:
				pass

		if ida_kernwin.ask_yn(1, f"Checkpoint address 0x{addr:X} not found in IDA database.\nOverwrite and start from beginning?") != 1:
			return -1
		return 0
	else:
		if ida_kernwin.ask_yn(1, "Output file exists but no checkpoint marker found.\nOverwrite and start from beginning?") != 1:
			return -1
		return 0

def format_time(seconds):
	m, s = divmod(int(seconds), 60)
	h, m = divmod(m, 60)
	if h == 0:
		if m == 0:
			return f"{s:2d}s"
		return f"{m:2d}m {s:2d}s"
	return f"{h:2d}h {m:2d}m {s:2d}s"

def request_decompile():
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
		
	funcs = list(idautils.Functions())
	total_funcs = len(funcs)

	start_idx = resolve_checkpoint(output_name, funcs)
	if start_idx == -1:
		print("Decompilation cancelled.")
		return

	start_time = time.time()
	last_time = start_time
	last_idx = start_idx
	avg_rate = None
	is_first_chunk = start_idx != 0

	print(f"Starting decompilation of {input_name} to {output_name}...")
	print(f"Total functions to process: {start_idx}/{total_funcs}")

	write_mode = "a" if start_idx > 0 else "w"
	with open(output_name, write_mode, encoding="utf-8", buffering=1024 * 1024 * 16) as f:
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
			if ida_kernwin.user_cancelled():
				print(f"Decompilation interrupted by user on address 0x{funcs[i]:X}.")
				break

			ea = funcs[i]
			cfunc = None
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
			finally:
				del cfunc
				if (i + 1) % 100 == 0:
					ida_hexrays.clear_cached_cfuncs()

			if (i + 1) % 1000 == 0 or (i + 1) == total_funcs:
				current_idx = i + 1
				gc.collect()
				f.flush()

				current_time = time.time()
				elapsed_since_last = current_time - last_time
				processed_since_last = current_idx - last_idx

				if is_first_chunk:
					is_first_chunk = False
					eta_str = ""
				elif processed_since_last > 0 and elapsed_since_last > 0:
					current_rate = processed_since_last / elapsed_since_last
					if avg_rate is None:
						avg_rate = current_rate
					else:
						avg_rate = 0.2 * current_rate + 0.8 * avg_rate

					remaining = total_funcs - current_idx
					eta_seconds = remaining / avg_rate
					eta_str = f"| ETA: {format_time(eta_seconds)} "
				else:
					eta_str = ""

				missed = current_idx - successful
				print(f"[{current_idx}/{total_funcs}] {(current_idx / total_funcs)*100:.1f}% {eta_str}| Chunk: {elapsed_since_last:.1f}s | Missed: {missed}")

				last_time = current_time
				last_idx = current_idx

	print("Decompilation finished!")

if __name__ == "__main__":
	request_decompile()
