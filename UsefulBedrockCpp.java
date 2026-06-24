import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.StringReader;
import java.nio.charset.Charset;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class UsefulBedrockCpp {
	private static final int USEFUL_PRIVATE_INSTRUCTION_SIZE = 384;
	private static final String[] IGNORED_NAMESPACES = new String[] {
		// private functions, thunk stubs
		"__sub__", "__thunks__",
		// 3rd party libraries (core, math, strings, utils)
		"nonstd", "std", "gsl", "tinystl", "absl", "glm", "csl", "ska", "moodycamel", "SFAT", "sigslot", "utf8", "unibrow", "msl",
		// 3rd party libraries (serialization, encoding, compression)
		"cereal", "bond_lite", "rapidjson", "rapidjson_cohtml", "rapidxml_cohtml", "snappy", "qrcodegen", "farmhashte", "farmhashnt", "farmhashsu", "farmhashsa",
		// networking & http transport
		"boost", "asio", "pplx", "websocketpp", "wspp_websocket_impl", "okhttp_websocket_impl", "web", "webrtc", "cricket", "rtc", "RakNet", "http_alloc_deleter", "http_header_compare",
		// ui & rendering backends
		"cohtml", "renoir", "cg", "msdfgen", "hbui", "bgfx", "bx", "bimg", "rendergraph", "dragon",
		// scripting engines & wrappers
		"v8", "v8_inspector", "v8_crdtp", "gametest", "Scripting", "OreUI",
		// telemetry, microsoft services, monetization
		"xbox", "Xal", "Microsoft", "PlayFab", "Social", "Realms", "RealmsAPI", "cll", "MinecraftEventing", "storeSearch", "sidebar",
		// internal debugging, crash logging & misc
		"google_breakpad", "logger", "SideBySide", "ViewT", "glTFExporter", "glTFExportData"
	};
	private static final String[] IGNORED_SPLIT_NAMESPACES = new String[] {
		"JsonUtil_*",
		// empty wrappers and type erasure
		"entt_any_cast", "entt_basic_any", "entt_meta_any", "entt_internal",
		// sub-namespaces of 3rd party libraries
		"Cereal*", "farmhash*", "Rak*", "WebRTC*", "WebSocket*", "Webview*",
		// telemetry & tracking
		"*Crash*", "*Telemetry*", "*Analytics*", "BedrockLog*"
	};
	private static final String[] SPLIT_NAMESPACES = new String[] {
		"std", "JsonUtil", "entt", "Bedrock",
	};
	private static final Pattern VALID_NAMESPACE_MATCHER = Pattern.compile("[a-zA-Z0-9_]+");

	private static void skipDeclarationChunk(BufferedReader reader) throws IOException {
		boolean foundFunctionChunk = false;
		boolean foundDataChunk = false;
		int newlineCounter = 0;

		String line;
		while ((line = reader.readLine()) != null) {
			if (line.length() == 0) {
				if ((++newlineCounter) >= 2 && foundFunctionChunk && foundDataChunk) {
					break;
				}
				continue;
			} else if (newlineCounter == 0) {
				continue;
			}

			if ("//-------------------------------------------------------------------------".equals(line)) {
				continue;
			} else if ("// Function declarations".equals(line)) {
				foundFunctionChunk = true;
			} else if ("// Data declarations".equals(line)) {
				foundDataChunk = true;
			} else if (line.startsWith("//----- (")) {
				throw new IllegalStateException("readDeclarationChunk: Instruction appeared too early -> " + line);
			} else if (foundFunctionChunk && newlineCounter != 1) {
				throw new IllegalStateException("readDeclarationChunk: Unexpected declaration line -> " + line);
			}
			newlineCounter = 0;
		}
	}

	private static String nextInstruction(BufferedReader reader) throws IOException {
		StringBuilder builder = new StringBuilder();
		builder.append(reader.readLine());
		builder.append('\n');

		StringBuffer buffer = new StringBuffer();
		boolean previousLineHasWhitespace = false;

		String line;
		while ((line = reader.readLine()) != null) {
			if (line.length() == 0) {
				if (!previousLineHasWhitespace) {
					break;
				}
				previousLineHasWhitespace = false;
			} else if (!previousLineHasWhitespace && line.charAt(0) == '/') {
				buffer.append(line);
				buffer.append('\n');
				continue;
			}

			if (!buffer.isEmpty()) {
				builder.append(buffer);
				buffer.delete(0, buffer.length());
			}
			builder.append(line);
			builder.append('\n');

			if (line.length() != 0) {
				previousLineHasWhitespace = Character.isWhitespace(line.charAt(0));
			}
		}

		return builder.toString();
	}

	private enum InstructionType { 
		USEFUL, THUNK, JUNK 
	}

	private static InstructionType classifyInstruction(String code) throws IOException {
		BufferedReader reader = new BufferedReader(new StringReader(code));

		String address = reader.readLine();
		if (!address.startsWith("//----- (")
				|| !address.endsWith(") --------------------------------------------------------")) {
			if (address.charAt(0) == '/' || address.charAt(0) == '#') {
				return InstructionType.JUNK;
			}
			throw new IllegalStateException("classifyInstruction: Unexpected address format -> " + address);
		}

		String line;
		boolean isThunk = false;
		while ((line = reader.readLine()) != null) {
			if (line.length() != 0 && line.charAt(0) != '/' && line.charAt(0) != '#') {
				break;
			}
			if ("// attributes: thunk".equals(line)) {
				isThunk = true;
			}
		}

		if (line != null) {
			if (isThunk || line.contains("virtual thunk to") || line.contains("__fastcall operator")) {
				return InstructionType.THUNK;
			}
			if (line.contains(" sub_") || line.contains("*sub_")) {
				boolean isVoidPtr = "void **sub_".equals(line.substring(0, Math.min(11, line.length())));
				boolean isTooSmall = code.length() < USEFUL_PRIVATE_INSTRUCTION_SIZE;
				
				if (isVoidPtr || isTooSmall) {
					return InstructionType.THUNK;
				}
				return InstructionType.USEFUL;
			}
		}

		return isThunk ? InstructionType.THUNK : (line != null ? InstructionType.USEFUL : InstructionType.JUNK);
	}

	private static class InstructionData {
		public final String namespace;
		public final String source;

		public InstructionData(String source, String namespace) {
			this.namespace = namespace;
			this.source = source;
		}

		public static InstructionData of(String source, boolean ignoreNamespaces) throws IOException {
			BufferedReader reader = new BufferedReader(new StringReader(source));

			String line;
			while ((line = reader.readLine()) != null) {
				if (line.length() == 0 || line.charAt(0) == '/') {
					continue;
				}
				break;
			}

			int parenthesesBrackets = 0, squareBrackets = 0, curlyBrackets = 0, angleBrackets = 0;
			boolean singleQuoted = false, doubleQuoted = false, backticked = false;

			boolean expectingParentheses = false, namespaced = false;
			StringBuffer buffer = new StringBuffer();
			for (char symbol : line.toCharArray()) {
				if (!singleQuoted && !doubleQuoted && !backticked && parenthesesBrackets == 0 && squareBrackets == 0
						&& curlyBrackets == 0 && angleBrackets == 0) {
					if (symbol == '(' && buffer.length() != 0) {
						break;
					}
					if (symbol == ' ') {
						// special case when operator used for return values via type conversion
						if (buffer.toString().endsWith("::operator")) {
							break;
						}
						buffer.delete(0, buffer.length());
						namespaced = false;
						continue;
					}
					// probably useful for analysis, but for now we can actually skip it
					if (buffer.length() == 0 && (symbol == '*' || symbol == '&')) {
						continue;
					}
					if (symbol == ':') {
						namespaced = true;
					}
				}
				if (expectingParentheses) {
					// even when we expecting enclosing scope, there could be bitwise operators
					// e.g. operator<<<std::char_traits<char>> or operator<<=
					if (symbol != '<' && symbol != '=') {
						angleBrackets++;
					}
					expectingParentheses = false;
				}
				switch (symbol) {
					case '\'': singleQuoted = !singleQuoted; break;
					case '"': doubleQuoted = !doubleQuoted; break;
					case '`': backticked = !backticked; break;
					case '(':
						// sometimes there is __fastcall which is prepended by bracket, still analyzable
						if (buffer.length() != 0) {
							parenthesesBrackets++;
						}
						break;
					case '[': squareBrackets++; break;
					case '{': curlyBrackets++; break;
					case ')': parenthesesBrackets--; break;
					case ']': squareBrackets--; break;
					case '}': curlyBrackets--; break;
					case '<':
						if (buffer.length() <= 10) {
							angleBrackets++;
						} else {
							String overload = buffer.toString();
							if (!(overload.endsWith("::operator") || overload.endsWith("::operator<"))) {
								angleBrackets++;
							} else {
								// there must be such cases when operator<< appears in comparison, not bitwise operation
								// e.g. operator<<Core::StackString<char,1024u>>
								expectingParentheses = overload.endsWith("::operator<");
							}
						}
						break;
					case '>':
						if (buffer.length() <= 10) {
							angleBrackets--;
						} else {
							String overload = buffer.toString();
							if (!(overload.endsWith("::operator") || overload.endsWith("::operator>")
									|| overload.endsWith("::operator-") || overload.endsWith("::operator<="))) {
								angleBrackets--;
							}
						}
						break;
				}
				buffer.append(symbol);
			}
			if (singleQuoted || doubleQuoted || backticked || parenthesesBrackets != 0 || squareBrackets != 0
					|| curlyBrackets != 0 || angleBrackets != 0) {
				throw new IllegalStateException("parseInstructionData: Expecting unnested instruction -> " + line);
			}

			String definition = buffer.toString();
			Matcher namespaceRegex = VALID_NAMESPACE_MATCHER.matcher(definition);
			if (!namespaceRegex.find()) {
				throw new IllegalStateException(
						"parseInstructionData: Invalid namespace definition -> " + definition + " (line " + line + ")");
			}

			String namespace = namespaceRegex.group();
			if (!namespaced) {
				namespace = namespace.startsWith("Java_") ? "__jni__" : "__sub__";
			}
			if (ignoreNamespaces && IGNORED_NAMESPACES.length != 0 && Arrays.stream(IGNORED_NAMESPACES).anyMatch(namespace::equals)) {
				return null;
			}
			if (SPLIT_NAMESPACES.length != 0 && Arrays.stream(SPLIT_NAMESPACES).anyMatch(namespace::equals)) {
				Matcher subMatcher = Pattern.compile(namespace + "::([a-zA-Z0-9_]+)(?:<|::)").matcher(definition);
				if (subMatcher.find()) {
					namespace = namespace + "_" + subMatcher.group(1);
				}
			}

			InstructionData data = new InstructionData(source, namespace);
			if (ignoreNamespaces && IGNORED_SPLIT_NAMESPACES.length != 0 && Arrays.stream(IGNORED_SPLIT_NAMESPACES).anyMatch(ignoredNs -> {
				if (ignoredNs.startsWith("*") && ignoredNs.endsWith("*")) {
					return data.namespace.contains(ignoredNs.substring(1, ignoredNs.length() - 1));
				} else if (ignoredNs.startsWith("*")) {
					return data.namespace.endsWith(ignoredNs.substring(1));
				} else if (ignoredNs.endsWith("*")) {
					return data.namespace.startsWith(ignoredNs.substring(0, ignoredNs.length() - 1));
				}
				return data.namespace.equals(ignoredNs);
			})) {
				return null;
			}
			return data;
		}
	}

	private static void rewriteInstructionChunk(BufferedReader reader, String outputFolder, boolean ignoreNamespaces) throws IOException {
		long beginning = System.currentTimeMillis();
		long instructions = 0l;
		long rewritten = 0l;

		boolean ignoreThunks = ignoreNamespaces && Arrays.stream(IGNORED_NAMESPACES).anyMatch("__thunks__"::equals);
		while (reader.ready()) {
			String instruction = nextInstruction(reader);
			InstructionType type = classifyInstruction(instruction);

			if (type == InstructionType.USEFUL) {
				InstructionData data = InstructionData.of(instruction, ignoreNamespaces);
				if (data != null) {
					File outputSource = new File(outputFolder, data.namespace + ".c");
					boolean alreadyExists = outputSource.exists();
					if (!alreadyExists) {
						outputSource.createNewFile();
					}

					FileWriter writer = new FileWriter(outputSource, Charset.forName("UTF-8"), true);
					if (alreadyExists) writer.write('\n');
					writer.write(data.source);
					writer.close();
					rewritten++;
				}
			} else if (type == InstructionType.THUNK && !ignoreThunks) {
				File thunksFile = new File(outputFolder, "__thunks__.c");
				boolean alreadyExists = thunksFile.exists();
				if (!alreadyExists) {
					thunksFile.createNewFile();
				}

				FileWriter writer = new FileWriter(thunksFile, Charset.forName("UTF-8"), true);
				if (alreadyExists) writer.write('\n');
				writer.write(instruction);
				writer.close();

				rewritten++; 
			}
			instructions++;
		}

		System.out.println("Rewritten " + rewritten + " of " + instructions + " instructions in "
				+ (System.currentTimeMillis() - beginning) + "ms!");
	}

	private static void deleteRecursive(File file) {
		if (file.isDirectory()) {
			for (File children : file.listFiles()) {
				deleteRecursive(children);
			}
		}
		file.delete();
	}

	public static void makeCppUseful(String inputSource, String outputFolder, boolean ignoreNamespaces) throws IOException {
		File inputFile = new File(inputSource);
		File outputFile = new File(outputFolder);
		if (outputFile.exists()) {
			File backupFile = new File(outputFolder + ".bak");
			if (backupFile.exists()) {
				deleteRecursive(backupFile);
			}
			outputFile.renameTo(backupFile);
		}
		outputFile.mkdirs();

		BufferedReader reader = new BufferedReader(new FileReader(inputSource, Charset.forName("UTF-8")));
		skipDeclarationChunk(reader);
		rewriteInstructionChunk(reader, outputFolder, ignoreNamespaces);
		try {
			reader.close();
		} catch (IOException e) {
		}

		double inputFileSize = inputFile.length();
		double outputFileSize = 0d;
		for (File outputChildren : outputFile.listFiles()) {
			outputFileSize += outputChildren.length();
		}
		System.out.println("Got " + (Math.floor(inputFileSize / outputFileSize * 1000d) / 10d) + "% compression ratio ("
				+ (Math.floor(inputFileSize / 1024d / 1024d * 10d) / 10d) + "MiB -> "
				+ (Math.floor(outputFileSize / 1024 / 1024 * 10) / 10) + "MiB).");
	}

	private static void flushDirectoryListing(String path) throws IOException {
		File outputData = new File(path);
		File outputListing = new File(path, "__index__");
		if (outputListing.exists()) {
			deleteRecursive(outputListing);
		}
		File[] files = outputData.listFiles();
		outputListing.createNewFile();

		FileWriter writer = new FileWriter(outputListing);
		for (File children : files) {
			String name = children.getName();
			if (name.endsWith(".c") && children.isFile()) {
				writer.write(name.substring(0, name.length() - 2));
				writer.write('\n');
			}
		}
		try {
			writer.close();
		} catch (IOException e) {
		}
	}

	public static void main(String[] args) {
		List<String> arguments = new ArrayList<>();
		String libraryName = null;
		for (String argument : args) {
			if (argument.startsWith("--")) {
				arguments.add(argument);
				continue;
			}
			if (libraryName != null) {
				throw new IllegalArgumentException("Library name was already providen (" + libraryName + "): " + argument + "!");
			}
			libraryName = argument;
		}
		if (libraryName == null || libraryName.length() == 0) {
			libraryName = "minecraftpe";
		}

		String outputDirectory = Path.of(libraryName).toString();
		try {
			boolean ignoreNamespaces = !arguments.contains("--full");
			if (!arguments.contains("--listing-only")) {
				makeCppUseful(Path.of("lib" + libraryName + ".so.c").toString(), outputDirectory, ignoreNamespaces);
			}
			if (arguments.contains("--listing") || arguments.contains("--listing-only")) {
				flushDirectoryListing(outputDirectory);
			}
		} catch (IOException e) {
			throw new RuntimeException(e);
		}
	}
}
