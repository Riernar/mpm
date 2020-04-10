"""
User Interface package

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
from copy import deepcopy
import logging

# Local import
from ..ui.impl import ModGUI, OverridesGUI

LOGGER = logging.getLogger("mpm.ui")


def assign_mods(packmodes, mods):
    """
    Assign mods to packmodes using a GUI. Might modify args in-place

    Arguments
        packmodes -- packmode definitions, the "packmodes" property
            of a pack_manifest
        mods -- mods definitions, the "mods" property of a pack manifest
            ! their names must be resolved !
    
    Return
        the new ('packmodes', 'mods')
    """
    LOGGER.info("Creating GUI for mods assignements")
    gui = ModGUI(deepcopy(packmodes), deepcopy(mods))
    gui.run()
    return gui.packmodes, gui.mod_list


def assign_overrides(packmodes, overrides, override_cache, added_override=None):
    """
    Assign overrides to packmodes using a GUI, and compact
    assignment

    Arguments
        packmodes -- "packmodes" property of a pack_manifest, the packmodes definitions
        overrides -- "overrides" property of a pack_manifest, overrides assignemnts to packmodes
        override_cache -- "overrides-cache" property of a pack_manifest, list of overrides filepath and hash
        added_override -- overrides that were just added and should not be already assigned by their parent folder
    
    Returns
        (packmodes, overrides)
        packmodes definition (some packmodes may be added in the GUI)
        overrides assignements to packmodes
    """
    LOGGER.info("Creating GUI for overrides assignements")
    gui = OverridesGUI(deepcopy(packmodes), override_cache, deepcopy(overrides), added_override)
    gui.run()
    return gui.packmodes, gui.overrides
