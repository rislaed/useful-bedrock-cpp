import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.StringReader;
import java.nio.charset.Charset;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class UsefulBedrockCpp {
	private static final int USEFUL_PRIVATE_INSTRUCTION_SIZE = 384 * 1024;
	private static final String[] IGNORED_NAMESPACES = new String[] {
		"acme", "asio", "bond_lite", "boost", "cll", "cohtml", "csl", "entt", "gsl", "moodycamel", "msl",
		"nonstd", "pplx", "rapidjson", "reflection", "renoir", "ska", "std", "type_id", "web", "websocketpp",
		"wspp_websocket_impl", "xbox", "Concurrency", "Microsoft", "PlayFab", "RakNet", "SharedPtr", "Xal"
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

	private static boolean isUsefulInstruction(String code) throws IOException {
		BufferedReader reader = new BufferedReader(new StringReader(code));

		String address = reader.readLine();
		if (!address.startsWith("//----- (")
				|| !address.endsWith(") --------------------------------------------------------")) {
			if (address.charAt(0) == '/' || address.charAt(0) == '#') {
				return false;
			}
			throw new IllegalStateException("isUsefulInstruction: Unexpected address format -> " + address);
		}

		String line;
		while ((line = reader.readLine()) != null) {
			if (line.length() != 0 && line.charAt(0) != '/' && line.charAt(0) != '#') {
				break;
			}
			if ("// attributes: thunk".equals(line)) {
				return false;
			}
		}

		if (line != null) {
			if (line.contains("virtual thunk to") || line.contains("__fastcall operator")) {
				return false;
			}
			if (line.contains(" sub_") || line.contains("*sub_")) {
				return !("void **sub_".equals(line.substring(0, 11)))
						&& code.length() >= USEFUL_PRIVATE_INSTRUCTION_SIZE;
			}
		}

		return line != null;
	}

	private static class InstructionData {
		public final String namespace;
		public final String source;

		public InstructionData(String source, String namespace) {
			this.namespace = namespace;
			this.source = source;
		}

		public static InstructionData of(String source) throws IOException {
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
					if (buffer.length() == 0 && (symbol == '*' && symbol == '&')) {
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
								// there must be such cases when operator<< appears in comparison, not bitwise
								// operation
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
			if (Arrays.stream(IGNORED_NAMESPACES).anyMatch(namespace::equals)) {
				return null;
			}
			if (!namespaced) {
				namespace = namespace.startsWith("Java_") ? "__jni__" : "__main__";
			}

			return new InstructionData(source, namespace);
		}
	}

	private static void rewriteInstructionChunk(BufferedReader reader, String outputFolder) throws IOException {
		long beginning = System.currentTimeMillis();
		long instructions = 0l;
		long rewritten = 0l;

		while (reader.ready()) {
			String instruction = nextInstruction(reader);
			if (isUsefulInstruction(instruction)) {
				InstructionData data = InstructionData.of(instruction);
				if (data != null) {
					File outputSource = new File(outputFolder, data.namespace + ".c");

					boolean alreadyExists = outputSource.exists();
					if (!alreadyExists) {
						try {
							outputSource.createNewFile();
						} catch (IOException e) {
							throw new RuntimeException("Cannot create " + data.namespace + " namespace file!");
						}
					}

					FileWriter writer = new FileWriter(outputSource, Charset.forName("UTF-8"), true);
					if (alreadyExists) {
						writer.write('\n');
					}
					writer.write(data.source);

					try {
						writer.close();
					} catch (IOException e) {
					}

					rewritten++;
				}
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

	public static void makeCppUseful(String inputSource, String outputFolder) throws IOException {
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
		rewriteInstructionChunk(reader, outputFolder);
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
		File outputListing = new File(path, "__index__.txt");
		if (outputListing.exists()) {
			deleteRecursive(outputListing);
		}
		outputListing.createNewFile();

		FileWriter writer = new FileWriter(outputListing);
		for (File children : outputData.listFiles()) {
			if (children.isFile()) {
				writer.write(children.getName());
				writer.write('\n');
			}
		}
		try {
			writer.close();
		} catch (IOException e) {
		}
	}

	public static void main(String[] args) {
		try {
			makeCppUseful(Path.of("libminecraftpe.so.c").toString(), Path.of("minecraftpe").toString());
			if (args.length > 0 && args[0] == "--listing") {
				flushDirectoryListing(Path.of("minecraftpe").toString());
			}
		} catch (IOException e) {
			throw new RuntimeException(e);
		}
	}
}
