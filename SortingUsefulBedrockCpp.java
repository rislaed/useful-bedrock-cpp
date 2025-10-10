import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Path;
import java.util.*;

public class SortingUsefulBedrockCpp {
	public static void main(String[] args) {
		File inputFolder = Path.of("minecraftpe").toFile();
		File outputFolder = Path.of("libminecraftpe").toFile();
		if (outputFolder.exists()) {
			File backupFile = new File(outputFolder + ".bak");
			if (backupFile.exists()) {
				deleteRecursive(backupFile);
			}
			outputFolder.renameTo(backupFile);
		}
		outputFolder.mkdirs();

		List<String> files = new ArrayList<>();
		for (File children : inputFolder.listFiles()) {
			if (children.isFile()) {
				files.add(children.getName());
			}
		}

		Map<String, List<String>> categorized = categorizeFiles(files);
		for (Map.Entry<String, List<String>> category : categorized.entrySet()) {
			File categoryFolder = new File(outputFolder, category.getKey());
			categoryFolder.mkdir();
			for (String children : category.getValue()) {
				File inputFile = new File(inputFolder, children);
				File outputFile = new File(categoryFolder, children);
				try {
					copyFile(inputFile, outputFile);
				} catch (IOException e) {
					System.out.println("Cannot copy file " + children + ": " + e);
				}
			}
		}

		System.out.println("Got " + categorized.keySet().size() + " categories written.");
	}

	private static void copyFile(File inputFile, File outputFile) throws IOException {
		FileInputStream inputStream = new FileInputStream(inputFile);
		FileOutputStream outputStream = new FileOutputStream(outputFile);
		byte[] buffer = new byte[16384];
		int length = -1;
		while ((length = inputStream.read(buffer, 0, 16384)) != -1) {
			outputStream.write(buffer, 0, length);
		}
		try {
			inputStream.close();
		} catch (IOException e) {
		}
		try {
			outputStream.close();
		} catch (IOException e) {
		}
	}

	private static void deleteRecursive(File file) {
		if (file.isDirectory()) {
			for (File children : file.listFiles()) {
				deleteRecursive(children);
			}
		}
		file.delete();
	}

	public static Map<String, List<String>> categorizeFiles(List<String> files) {
		Map<String, List<String>> categories = new HashMap<>();

		for (String file : files) {
			String category = determineCategory(file);
			categories.computeIfAbsent(category, k -> new ArrayList<>()).add(file);
		}

		return categories;
	}

	private static final Set<String> MOB_NAMES = Set.of(
			"Zombie", "Skeleton", "Creeper", "Spider", "Enderman", "Slime", "Ghast", "Blaze",
			"Witch", "Guardian", "Shulker", "WitherBoss", "EnderDragon", "Piglin", "Hoglin",
			"Phantom", "Ravager", "Vindicator", "Evoker", "Pillager", "Drowned", "Husk",
			"Stray", "Vex", "Silverfish", "Endermite", "CaveSpider", "MagmaCube", "ZombieVillager",
			"Wolf", "Ocelot", "Cat", "Parrot", "Dolphin", "Panda", "Fox", "Bee", "Llama",
			"TraderLlama", "PolarBear", "Rabbit", "Turtle", "Pufferfish", "Salmon", "Cod",
			"TropicalFish", "Squid", "Axolotl", "Goat", "Frog", "Tadpole", "Allay", "Warden",
			"Bat", "Chicken", "Cow", "Donkey", "Horse", "Mule", "Mooshroom", "Sheep", "SnowGolem",
			"IronGolem", "Villager", "WanderingTrader", "Strider", "PiglinBrute", "IllagerBeast",
			"Agent", "Arrow", "ArmorStand", "Balloon", "Boat", "EnderCrystal", "EnderMan", "ThrownEgg",
			"Minecart", "FishingHook", "Pig");

	private static String determineCategory(String filename) {
		String nameWithoutExt = filename.replace(".c", "");

		if (filename.endsWith("Block.c") || filename.contains("Block") || nameWithoutExt.startsWith("Block")) {
			return "Blocks";
		}

		if (filename.endsWith("Item.c") || filename.contains("Item") || nameWithoutExt.startsWith("Item")) {
			return "Items";
		}

		if (isMobFile(nameWithoutExt)) {
			return "Entities";
		}

		if (filename.endsWith("Mob.c") || filename.contains("Mob") || filename.endsWith("Animal.c") ||
				filename.endsWith("Actor.c") || filename.contains("Actor") || nameWithoutExt.startsWith("Actor") ||
				filename.contains("Entity") || nameWithoutExt.startsWith("Entity")
				|| filename.contains("Animal") || filename.contains("Skin")) {
			return "Actors";
		}

		if (filename.endsWith("Player.c") || filename.contains("Player") || nameWithoutExt.startsWith("Player")) {
			return "Player";
		}

		if (filename.endsWith("Command.c") || filename.contains("Command") || nameWithoutExt.startsWith("Command")) {
			return "Commands";
		}

		if (filename.endsWith("Packet.c") || filename.contains("Packet") || nameWithoutExt.startsWith("Packet") ||
				filename.contains("Network") || nameWithoutExt.startsWith("Network") ||
				filename.contains("Rak") || filename.contains("Protocol")) {
			return "Network";
		}

		if (filename.endsWith("Component.c") || filename.contains("Component") || nameWithoutExt.startsWith("Component")
				|| filename.contains("Trigger") || filename.endsWith("System.c") || filename.contains("System")
				|| nameWithoutExt.startsWith("System")) {
			return "GameSystems";
		}

		if (filename.endsWith("Event.c") || filename.contains("Event") || nameWithoutExt.startsWith("Event") ||
				filename.contains("Listener") || filename.contains("Handler")) {
			return "Events";
		}

		if (filename.endsWith("Behavior.c") || filename.contains("Behavior") || nameWithoutExt.startsWith("Behavior") ||
				filename.endsWith("Goal.c") || filename.contains("Goal") || nameWithoutExt.startsWith("Goal") ||
				filename.contains("AI") || filename.contains("Navigation") || nameWithoutExt.contains("Definition") ||
				filename.contains("Path")) {
			return "AI";
		}

		if (filename.endsWith("Renderer.c") || filename.contains("Render") || nameWithoutExt.startsWith("Render") ||
				filename.endsWith("Model.c") || filename.contains("Model") ||
				filename.endsWith("Texture.c") || filename.contains("Texture") ||
				filename.endsWith("Shader.c") || filename.contains("Shader") ||
				filename.endsWith("Material.c") || filename.contains("Material") ||
				filename.contains("Graphics") || filename.contains("Visual") ||
				filename.contains("Camera") || filename.contains("Frustum")) {
			return "Rendering";
		}

		if (filename.endsWith("Particle.c") || filename.contains("Particle") ||
				filename.endsWith("Animation.c") || filename.contains("Animation")) {
			return "VisualEffects";
		}

		if (filename.contains("ScreenController")) {
			return "ScreenControllers";
		}

		if (filename.contains("UI") || filename.contains("Screen") || filename.contains("Dialog") ||
				filename.contains("HUD") || filename.contains("Interface") ||
				filename.endsWith("Container.c") || filename.contains("Container") ||
				filename.contains("Controller") || filename.contains("Button") ||
				filename.contains("Menu") || filename.contains("Layout") || filename.contains("Scene")) {
			return "UI";
		}

		if (filename.contains("Sound") || filename.contains("Audio") || filename.contains("Music") ||
				filename.endsWith("SoundPlayer.c") || filename.contains("Voice")) {
			return "Audio";
		}

		if (filename.contains("World") || filename.contains("Level") || filename.contains("Chunk") ||
				filename.contains("Biome") || filename.contains("Dimension") ||
				filename.contains("Terrain") || filename.contains("Structure") ||
				filename.contains("Piece") || filename.contains("Start") ||
				filename.contains("Village") || filename.contains("Monument") ||
				filename.contains("Mansion") || filename.contains("Fortress") ||
				filename.contains("Temple") || filename.contains("Mineshaft")) {
			return "World";
		}

		if (filename.contains("Feature") || filename.contains("Generator") || filename.contains("Generation") ||
				filename.contains("Noise") || filename.contains("Layer") || filename.contains("Surface")) {
			return "WorldGeneration";
		}

		if (filename.contains("Inventory") || filename.contains("Craft") || filename.contains("Recipe") ||
				filename.contains("Enchant") || filename.contains("Effect") || filename.contains("Potion") ||
				filename.contains("Trade") || filename.contains("Loot") || filename.contains("Store") ||
				filename.contains("Abilit") || filename.contains("Attribute") || filename.contains("Damage") ||
				filename.contains("Movement") || filename.contains("Physics") || filename.contains("Collision") ||
				filename.contains("Boss")) {
			return "Gameplay";
		}

		if (filename.contains("Script") || nameWithoutExt.startsWith("Script") || filename.contains("Molang")
				|| filename.contains("Expression")) {
			return "Scripting";
		}

		if (filename.contains("Data") || filename.contains("Storage") || filename.contains("File") ||
				filename.contains("Database") || filename.contains("JSON") || filename.contains("NBT") ||
				filename.contains("Serializ") || filename.contains("Config") || filename.contains("Setting") ||
				filename.contains("Property") || filename.contains("Tag") || filename.contains("Content") ||
				filename.contains("Resource") || filename.contains("Pack")) {
			return "Data";
		}

		if (filename.contains("Util") || filename.contains("Utility") || filename.contains("Helper") ||
				filename.contains("Manager") || filename.contains("Factory") || filename.contains("Registry") ||
				filename.contains("Math") || filename.contains("Random") || filename.contains("Vector") ||
				filename.contains("Matrix") || filename.contains("Geometry") || filename.contains("Bounds") ||
				filename.contains("AABB") || filename.contains("Color") || filename.contains("String") ||
				filename.contains("Array") || filename.contains("List") || filename.contains("Map") ||
				filename.contains("Set") || filename.contains("Queue") || filename.contains("Stack") ||
				filename.contains("Tree") || filename.contains("Graph") || filename.contains("Buffer") ||
				filename.contains("Stream") || filename.contains("Timer") || filename.contains("Clock") ||
				filename.contains("Hit")) {
			return "Utilities";
		}

		if (filename.contains("Debug") || filename.contains("Test") || filename.contains("Log") ||
				filename.contains("Profiler") || filename.contains("Performance") || filename.contains("Metric") ||
				filename.contains("Telemetry") || filename.contains("Analytics") || filename.contains("Crash")) {
			return "Debug";
		}

		if (filename.contains("Input") || filename.contains("Control") || filename.contains("Device") ||
				filename.contains("Keyboard") || filename.contains("Mouse") || filename.contains("Touch") ||
				filename.contains("Gamepad") || filename.contains("Controller") || filename.contains("Mapping") ||
				filename.contains("Binding")) {
			return "Input";
		}

		if (filename.contains("Commerce") || filename.contains("Marketplace") || filename.contains("Store") ||
				filename.contains("Purchase") || filename.contains("Transaction") || filename.contains("Payment") ||
				filename.contains("Currency") || filename.contains("Economy") || filename.contains("Price") ||
				filename.contains("Offer") || filename.contains("Product") || filename.contains("Inventory") ||
				filename.contains("Catalog") || filename.contains("Shop") || filename.contains("Sale")) {
			return "Commerce";
		}

		if (filename.contains("Education") || filename.contains("Edu") || filename.contains("Lesson") ||
				filename.contains("Tutorial") || filename.contains("Instruction") || filename.contains("Learning") ||
				filename.contains("Classroom") || filename.contains("School") || filename.contains("Course")) {
			return "Education";
		}

		if (filename.contains("Social") || filename.contains("Friend") || filename.contains("Party") ||
				filename.contains("Group") || filename.contains("Club") || filename.contains("Community") ||
				filename.contains("Chat") || filename.contains("Message") || filename.contains("Profile") ||
				filename.contains("Avatar") || filename.contains("Persona") || filename.contains("Platform") ||
				filename.contains("Xbox") || filename.contains("Realms") || filename.contains("Account") ||
				filename.contains("Social") || filename.contains("Authentication") || filename.contains("Xbl") ||
				filename.contains("Store") || filename.contains("Purchase") || filename.contains("Commerce") ||
				filename.contains("Certificate") || filename.contains("Crypto") || filename.contains("Security") ||
				filename.contains("Service") || filename.contains("Api") || filename.contains("Web") ||
				filename.contains("Http") || filename.contains("HTTP") || filename.contains("Online")) {
			return "Social";
		}

		return "Other";
	}

	private static boolean isMobFile(String nameWithoutExt) {
		if (MOB_NAMES.contains(nameWithoutExt)) {
			return true;
		}

		for (String mobName : MOB_NAMES) {
			if (nameWithoutExt.contains(mobName)
					&& nameWithoutExt.length() > nameWithoutExt.indexOf(mobName) + mobName.length()) {
				char nextChar = nameWithoutExt.charAt(nameWithoutExt.indexOf(mobName) + mobName.length());
				if (Character.isUpperCase(nextChar)) {
					return true;
				}
			}
		}

		return false;
	}
}
