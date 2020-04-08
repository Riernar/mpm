Pack manager for Minecraft
==========================

WIP modpack manager for minecraft. Aims at simplifying modpack releases, updates and server updates.
Main features include:
- "Packmodes" to easily differentiate client-only mods from server mods, or have a lite version of the pack
- Auto-update modpack on client launch
- Updates based on diffs are faster than a dumb copy-paste
- Update from a webserver/git repo. Client are always in sync with the minecraft server version
- Update over FTP for minecraft servers
- Compatible with the curse modpack format
- Curse .zip creation for all packmodes
- Curse .zip creation with itself included, ready to use for auto-updates

> Not functional yet

# Planned features
- [X] assign mods & overrides to "packmodes" (e.g. "server", "client-lite", "client-full")
    + this allows a modular pack and distinctin between server element and client-side-only elements (resources, resource-pack ...)
- [ ] easily deploy modpack update
    + [ ] leverage curse modpack
    + [X] assign mods to a packmode using a GUI
    + [X] assign overrides to a packmode using a GUI
    + [ ] generate server files
- [ ] update a modpack to new version and packmodes using command-line
    + [X] smart update that only deletes or download needed files
    + [ ] include update over FTP for easy server deployment
    + [ ] support update with a web-server for overrides
    + [ ] support update using the full pack .zip
- [ ] compatibility with curse modpack format
    + [ ] create .zip for modpack first install
- [X] use a new manifest format to support features
