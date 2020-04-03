Pack manager for Minecraft
==========================

WIP pack manager for minecraft. Allows to auto-update minecraft modpacks before launch.

> Not functional yet

# Planned features
- [ ] assign mods & overrides to "packmodes" (e.g. "server", "client-lite", "client-full")
    + this allows a modular pack and distinctin between server element and client-side-only elements (resources, resource-pack ...)
- [ ] easily deploy modpack update
    + [ ] leverage curse modpack
    + [X] assign mods to a packmode using a GUI
    + [ ] assign overrides to a packmode using a GUI
    + [ ] generate server files
- [ ] update a modpack to new version and packmodes using command-line
    + [ ] smart update that only deletes or download needed files
    + [ ] include update over FTP for easy server deployment
    + [ ] support update with a web-server for overrides
    + [ ] support update using the full pack .zip
- [ ] compatibility with curse modpack format
    + [ ] create .zip for modpack first install
- [ ] use a new manifest format to support features
