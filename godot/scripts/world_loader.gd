# file generated with AI assistance: Claude Code - 2026-10-22 22:09:22 UTC
class_name WorldLoader
extends RefCounted
## Opens a built world, a directory with world.json, the glb tiles, the
## horizon and the tree files or the same files in a .world package (a
## ZIP), and loads its scenes. open() reads and checks the manifest only;
## load_scene() loads one glTF file of the world, read_bytes() any other. Callers never build file paths
## themselves, so both sources go through the same calls. find_worlds()
## lists the worlds to choose from, routes() a world's routes, args() the
## launcher arguments (--world, --start, --route).

## the default world (`make world`, W=stuttgart) of a checkout, relative
## to the Godot project (res://)
const DEFAULT_DIR := "../data/out/worlds/stuttgart"
## a directory that exists only in a checkout, relative to res://
const CHECKOUT_MARK := "../worlds"
## the world directory an export looks for next to its executable
const EXE_WORLD := "world"
const MANIFEST := "world.json"
const SCHEMA := 1
## searched by find_worlds() after user://worlds, relative to res://
const REPO_WORLDS := ["../data/out/worlds", "../data/out/packages"]
## colon-separated directories find_worlds() searches last
const WORLDS_ENV := "HEIMSTRECKE_WORLDS"
const USER_WORLDS := "user://worlds"
## user routes of a world: user://routes/<world id>/<route id>.json
const USER_ROUTES := "user://routes"
const PACKAGE_SUFFIX := ".world"
## static functions cannot name their own class without the class cache
const SCRIPT_PATH := "res://scripts/world_loader.gd"

## the parsed world.json after a successful open()
var manifest: Dictionary = {}
## the reason of the last failed open(), empty after success
var error := ""
## the opened directory or .world file, empty when nothing is open
var path: String:
	get:
		return _path
## true when the opened world is a .world package
var is_package: bool:
	get:
		return _zip != null

var _path := ""
var _zip: ZIPReader


## The default world: the first of default_candidates() that exists (a
## directory with world.json or a file), else the last candidate, so
## open() names it in its error.
static func default_path() -> String:
	var candidates := default_candidates()
	for candidate in candidates:
		if FileAccess.file_exists(candidate.path_join(MANIFEST)) \
				or FileAccess.file_exists(candidate):
			return candidate
	return candidates[-1]


## Where default_path() looks, in order: world/ next to the executable,
## on macOS world/ next to the .app, and in the editor or a checkout
## (godot --path godot) the repository's data/out/worlds/stuttgart.
static func default_candidates() -> Array[String]:
	var found: Array[String] = []
	for dir in _exe_dirs():
		found.append(dir.path_join(EXE_WORLD))
	var project := ProjectSettings.globalize_path("res://")
	if OS.has_feature("editor") or DirAccess.dir_exists_absolute(
			project.path_join(CHECKOUT_MARK).simplify_path()):
		found.append(project.path_join(DEFAULT_DIR).simplify_path())
	return found


## The launcher arguments after --, each as `--name value` or
## `--name=value`: {world (absolute path, "" when absent), start (start
## point index, -1 when absent), route (route id, "" when absent), reverse
## (the flag `--reverse`: drive the route from its last point)}. Other
## arguments are left to the caller.
static func args() -> Dictionary:
	var argv := OS.get_cmdline_user_args()
	var result := {"world": "", "start": -1, "route": "", "reverse": false}
	for i in argv.size():
		var key := argv[i]
		if key == "--reverse":
			result.reverse = true
			continue
		var value := ""
		var eq := key.find("=")
		if eq > 0:
			value = key.substr(eq + 1)
			key = key.substr(0, eq)
		elif i + 1 < argv.size():
			value = argv[i + 1]
		else:
			continue
		match key:
			"--world":
				result.world = absolute_path(value)
			"--start":
				if value.is_valid_int():
					result.start = int(value)
				else:
					push_error("--start needs a start index: " + value)
			"--route":
				result.route = value
	return result


## The value after --world in the user arguments (after --) as an
## absolute path (absolute_path()), or `fallback`.
static func path_from_args(fallback: String) -> String:
	var world: String = args().world
	return world if not world.is_empty() else fallback


## The worlds to choose from as [{path, is_package, manifest, error}],
## from user://worlds, the directory of the executable (on macOS also the
## one of the .app: .world files and world directories such as world/),
## the repository's data/out/worlds/* and data/out/packages/*.world and
## every directory in HEIMSTRECKE_WORLDS, in that order, each path once;
## sorted by name, then version. A world that does not open has an empty
## manifest and the reason in `error`.
static func find_worlds() -> Array[Dictionary]:
	var dirs: Array[String] = [ProjectSettings.globalize_path(USER_WORLDS)]
	dirs.append_array(_exe_dirs())
	for dir: String in REPO_WORLDS:
		dirs.append(ProjectSettings.globalize_path("res://") \
			.path_join(dir).simplify_path())
	for dir in OS.get_environment(WORLDS_ENV).split(":", false):
		dirs.append(absolute_path(dir))
	var seen := {}
	var worlds: Array[Dictionary] = []
	var loader: RefCounted = load(SCRIPT_PATH).new()
	for dir in dirs:
		for candidate in _candidates(dir):
			if seen.has(candidate):
				continue
			seen[candidate] = true
			loader.open(candidate)
			worlds.append({"path": candidate,
				"is_package": FileAccess.file_exists(candidate),
				"manifest": loader.manifest, "error": loader.error})
			loader.close()
	worlds.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var by_name := _name_of(a).naturalnocasecmp_to(_name_of(b))
		if by_name != 0:
			return by_name < 0
		return str(a.manifest.get("version", "")).naturalnocasecmp_to(
			str(b.manifest.get("version", ""))) < 0)
	return worlds


## The routes of a world manifest: its built-in route as id "world" (if
## it has one), then every valid user://routes/<world id>/<id>.json
## ({schema: 1, name, points, waypoints}, the id is the file name), each
## as {id, name, points, waypoints}.
static func routes_of(world: Dictionary) -> Array[Dictionary]:
	var routes: Array[Dictionary] = []
	var name := str(world.get("name", world.get("id", "")))
	if world.get("route") is Array and not world.route.is_empty():
		var waypoints: Variant = world.get("waypoints")
		routes.append({"id": "world", "name": name, "points": world.route,
			"waypoints": waypoints if waypoints is Array else []})
	var id := str(world.get("id", ""))
	var dir := USER_ROUTES.path_join(id)
	if id.is_empty() or not DirAccess.dir_exists_absolute(dir):
		return routes
	var files := Array(DirAccess.get_files_at(dir))
	files.sort()
	for file: String in files:
		if not file.ends_with(".json"):
			continue
		var data: Variant = JSON.parse_string(
			FileAccess.get_file_as_string(dir.path_join(file)))
		if not data is Dictionary or data.get("schema") != float(SCHEMA) \
				or not data.get("name") is String \
				or not data.get("points") is Array \
				or data.points.size() < 2 \
				or not data.get("waypoints") is Array:
			push_warning("invalid route file: " + dir.path_join(file))
			continue
		routes.append({"id": file.get_basename(), "name": data.name,
			"points": data.points, "waypoints": data.waypoints})
	return routes


## The directory of the executable and, on macOS, the one holding the
## .app (<dir>/Name.app/Contents/MacOS/<binary>).
static func _exe_dirs() -> Array[String]:
	var exe_dir := OS.get_executable_path().get_base_dir()
	var dirs: Array[String] = [exe_dir]
	if OS.get_name() == "macOS":
		dirs.append(exe_dir.get_base_dir().get_base_dir().get_base_dir())
	return dirs


## Package files and directories with a world.json directly in `dir`.
static func _candidates(dir: String) -> Array[String]:
	var found: Array[String] = []
	if not DirAccess.dir_exists_absolute(dir):
		return found
	for file in DirAccess.get_files_at(dir):
		if file.ends_with(PACKAGE_SUFFIX):
			found.append(dir.path_join(file))
	for sub in DirAccess.get_directories_at(dir):
		if FileAccess.file_exists(dir.path_join(sub).path_join(MANIFEST)):
			found.append(dir.path_join(sub))
	return found


## Sort name of a find_worlds() entry: the manifest name, else the file.
static func _name_of(world: Dictionary) -> String:
	return str(world.manifest.get("name", world.manifest.get("id",
		str(world.path).get_file())))


## `value` made absolute: a relative path is taken relative to the
## directory Godot was started from, PWD of the calling shell, because
## Godot itself changes into the project directory (--path).
static func absolute_path(value: String) -> String:
	if value.is_absolute_path():
		return value.simplify_path()
	var cwd := OS.get_environment("PWD")
	if cwd.is_empty():
		cwd = DirAccess.open(".").get_current_dir()
	return cwd.path_join(value).simplify_path()


## Opens the world at `source`, a .world package (a ZIP, see the README)
## or a directory, and checks its world.json; `verify` also checks the
## SHA-256 of every package entry against the manifest's `files`. On
## failure `error` says why and the return value is not OK.
func open(source: String, verify := false) -> Error:
	close()
	manifest = {}
	error = ""
	var err := _open_package(source, verify) \
		if source.ends_with(".world") and FileAccess.file_exists(source) \
		else _open_dir(source)
	if err != OK:
		close()
		manifest = {}
		return err
	_path = source
	return OK


## Closes an opened package; open() calls it first.
func close() -> void:
	if _zip != null:
		_zip.close()
		_zip = null
	_path = ""


## The world's name from the manifest, else its id.
func display_name() -> String:
	return str(manifest.get("name", manifest.get("id", "")))


## The attribution of the world's data sources, empty for older worlds.
func attribution() -> String:
	return str(manifest.get("attribution", ""))


## The routes of the opened world, see routes_of().
func routes() -> Array[Dictionary]:
	return routes_of(manifest)


## Loads the glTF file `name` (a tile or the horizon) of the opened world;
## null after an error.
func load_scene(name: String) -> Node:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var file := _path.path_join(name)
	var err := ERR_FILE_NOT_FOUND
	if is_package:
		file = "%s:%s" % [_path, name]
		var bytes := _zip.read_file(name)
		if not bytes.is_empty():
			err = doc.append_from_buffer(bytes, "", state)
			state.scene_name = name.get_basename()
	elif not _path.is_empty():
		err = doc.append_from_file(file, state)
	if err != OK:
		push_error("cannot load " + file)
		return null
	return doc.generate_scene(state)


## The bytes of the file `name` of the opened world (the tree files of
## trees.gd); empty after an error.
func read_bytes(name: String) -> PackedByteArray:
	if is_package:
		return _zip.read_file(name) if _zip.get_files().has(name) \
			else PackedByteArray()
	if _path.is_empty():
		return PackedByteArray()
	return FileAccess.get_file_as_bytes(_path.path_join(name))


## The non-empty <tile>.trees and <tile>.trunks files the manifest lists,
## none for a world without trees.
func _tree_files() -> Array[String]:
	var files: Array[String] = []
	var trees: Variant = manifest.get("trees")
	if trees is Dictionary:
		for tile: Dictionary in trees.get("tiles", []):
			var count := 0
			for counts: Array in tile.counts:
				for n: int in counts:
					count += n
			if count > 0:
				files.append(str(tile.name) + ".trees")
			if tile.trunks > 0:
				files.append(str(tile.name) + ".trunks")
	return files


func _open_dir(dir: String) -> Error:
	if not DirAccess.dir_exists_absolute(dir):
		error = "world data missing: %s (build it first, see README)" % dir
		return ERR_FILE_NOT_FOUND
	var file := dir.path_join(MANIFEST)
	if not FileAccess.file_exists(file):
		error = "world data missing: %s (build it first, see README)" % file
		return ERR_FILE_NOT_FOUND
	return _check_manifest(FileAccess.get_file_as_string(file), file)


func _open_package(file: String, verify: bool) -> Error:
	_zip = ZIPReader.new()
	var err := _zip.open(file)
	if err != OK:
		_zip = null
		error = "cannot open package (%s): %s" % [error_string(err), file]
		return ERR_FILE_CANT_OPEN
	var entries := _zip.get_files()
	if not entries.has(MANIFEST):
		error = "package has no %s: %s" % [MANIFEST, file]
		return ERR_FILE_NOT_FOUND
	err = _check_manifest(
		_zip.read_file(MANIFEST).get_string_from_utf8(), file)
	if err != OK:
		return err
	for name: Variant in manifest.tiles + [manifest.horizon] \
			+ _tree_files():
		if not entries.has(str(name)):
			error = "package is missing %s: %s" % [name, file]
			return ERR_FILE_NOT_FOUND
	if not verify:
		return OK
	var sums: Variant = manifest.get("files")
	if not sums is Dictionary:
		error = "package manifest has no files checksums: %s" % file
		return ERR_INVALID_DATA
	for name: String in sums:
		var ctx := HashingContext.new()
		ctx.start(HashingContext.HASH_SHA256)
		ctx.update(_zip.read_file(name) if entries.has(name) \
			else PackedByteArray())
		if ctx.finish().hex_encode() != str(sums[name]).to_lower():
			error = "checksum mismatch for %s: %s" % [name, file]
			return ERR_FILE_CORRUPT
	return OK


## Parses and checks the manifest text; `where` names it in errors.
func _check_manifest(text: String, where: String) -> Error:
	var data: Variant = JSON.parse_string(text)
	if not data is Dictionary or not data.get("tiles") is Array \
			or not data.get("horizon") is String:
		error = "invalid world.json: %s" % where
		return ERR_PARSE_ERROR
	var schema: Variant = data.get("schema")
	if not (schema is float or schema is int) or schema != SCHEMA:
		error = "unsupported world schema %s: %s" % [
			int(schema) if schema is float else schema, where]
		return ERR_FILE_UNRECOGNIZED
	if data.has("min_game"):
		var game := str(ProjectSettings.get_setting(
			"application/config/version", "0.0.0"))
		var need := _version(data.min_game)
		if need.is_empty():
			error = "invalid min_game %s: %s" % [data.min_game, where]
			return ERR_PARSE_ERROR
		if need > _version(game):
			error = "world needs game %s, this is %s: %s" % [
				data.min_game, game, where]
			return ERR_UNAVAILABLE
	manifest = data
	return OK


## MAJOR[.MINOR[.PATCH]] as three ints, missing parts 0 ("1" is
## [1, 0, 0]); [] when it is empty or a part is not a number.
static func _version(value: Variant) -> Array[int]:
	var parts: Array[int] = []
	var fields := str(value).split(".")
	if not value is String or fields.size() > 3:
		return parts
	for field in fields:
		if field.is_empty() or not field.is_valid_int() or field[0] in "+-":
			return []
		parts.append(int(field))
	while parts.size() < 3:
		parts.append(0)
	return parts
# - revised 2026-10-22 (default world under data/out/worlds/stuttgart)
# - revised 2026-10-22 (.world packages, --world argument)
# - revised 2026-10-22 (find_worlds, routes, args)
# - revised 2026-10-22 (versions with one to three parts)
# - revised 2026-10-22 (worlds next to the executable, --name=value)
# - revised 2026-10-23 (tree files, read_bytes)
