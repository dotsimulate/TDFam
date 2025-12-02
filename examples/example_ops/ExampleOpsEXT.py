"""
ExampleOpsEXT - Theme-switching operator family example using ActionOp pattern.

Demonstrates how to create "action operators" that execute behavior when clicked
in the TAB menu WITHOUT placing an operator. The menu stays open for quick
workflow actions.

SETUP:
    1. Create installer COMP with parentshortcut "EXAMPLE"
    2. Add custom_operators/ base inside it containing:

       THEME OPERATORS (ActionOp - won't place, just execute):
       - dark       (any COMP - tagged "actionEXAMPLE")
       - light      (any COMP - tagged "actionEXAMPLE")

       REGULAR OPERATORS (will place normally):
       - info_display   (container COMP)
       - color_swatch   (container COMP)

    3. Copy install_scripts/ folder from opfam-create
    4. Attach this extension to the installer COMP

USAGE:
    # From TAB menu:
    # - Click "dark" or "light" -> changes family color, menu stays open
    # - Click any other op -> places it normally

    # From code:
    op.EXAMPLE.Install()
    op.EXAMPLE.SetTheme('dark')
    op.EXAMPLE.ToggleTheme()

ActionOp PATTERN:
    In PlaceOp hook, return:
    - True  -> proceed with normal placement
    - False -> cancel placement, close menu
    - None  -> cancel placement, KEEP MENU OPEN (ActionOp!)
"""

OpFamCreateExt = mod('install_scripts/installer').OpFamCreateExt
tag_operators = mod('install_scripts/src/tag_helpers').tag_operators


class ExampleOpsEXT(OpFamCreateExt):
    """
    Example operator family with theme-switching ActionOps.

    Demonstrates the ActionOp pattern where certain menu items
    execute actions instead of placing operators.
    """

    THEMES = {
        'dark': {
            'family_color': [0.12, 0.12, 0.15],
            'label': 'Dark Theme',
        },
        'light': {
            'family_color': [0.85, 0.85, 0.8],
            'label': 'Light Theme',
        },
        'ice': {
            'family_color': [0.25, 0.45, 0.5],
            'label': 'Ice Theme',
        },
        'volcano': {
            'family_color': [0.85, 0.35, 0.15],
            'label': 'Volcano Theme',
        },
    }

    # Operators tagged with this are ActionOps (don't place, just execute)
    ACTION_TAG = 'actionEXAMPLE'

    def __init__(self, ownerComp):
        debug('ExampleOpsEXT.__init__ starting')

        # Read family name from parameter (like ChatInstallerEXT pattern)
        family_name = ownerComp.par.Family.eval()
        debug(f'Family name from par.Family: {family_name}')

        # Current theme
        self.theme = 'dark'
        theme_color = self.THEMES[self.theme]['family_color']
        debug(f'Initial theme: {self.theme}, color: {theme_color}')

        super().__init__(
            ownerComp=ownerComp,
            family_name=family_name,
            color=theme_color,
            compatible_types=['COMP', 'TOP', 'CHOP', 'SOP', 'DAT', 'MAT'],
        )

        # Auto-tag operators in custom_operators
        debug('Tagging operators in custom_operators')
        tag_operators(self)

        # Load config (without themes by default)
        debug('Loading operator config')
        self.themes_visible = False
        self._load_default_config()

        # ActionOps: theme keys + show_themes toggle + see_options + extras
        self.action_ops = set(self.THEMES.keys())
        self.action_ops.add('show_themes')
        self.action_ops.add('see_options')
        self.action_ops.add('random')
        self.action_ops.add('dotsimulate')
        self.action_ops.add('check_time')
        debug(f'ActionOps registered: {self.action_ops}')
        debug('ExampleOpsEXT.__init__ complete')

    # ==================== Public API ====================

    def Install(self):
        """
        Toggle installation based on par.Install state.
        Calls super().Install() or super().Uninstall() accordingly.
        """
        if self.ownerComp.par.Install:
            debug('ExampleOpsEXT.Install: Installing')
            super().Install()
        else:
            debug('ExampleOpsEXT.Install: Uninstalling')
            super().Uninstall()

    def SetTheme(self, theme_name):
        """
        Switch theme and update family color in TAB menu.

        Args:
            theme_name: 'dark', 'light', or 'ocean'
        """
        debug(f'SetTheme called with: {theme_name}')

        if theme_name not in self.THEMES:
            debug(f"Unknown theme '{theme_name}'. Options: {list(self.THEMES.keys())}")
            return

        self.theme = theme_name
        theme = self.THEMES[theme_name]
        self.color = theme['family_color']
        debug(f"Theme set to '{theme_name}', color: {self.color}")

        # Re-inject to update family color in menu
        debug('Updating family color in UI')
        self.ui.update_family_color(self.color)

        debug(f"Switched to {theme['label']}")

    def ToggleTheme(self):
        """Toggle between dark and light themes."""
        new_theme = 'light' if self.theme == 'dark' else 'dark'
        debug(f'ToggleTheme: {self.theme} -> {new_theme}')
        self.SetTheme(new_theme)

    def ToggleThemesVisible(self):
        """Toggle themes visibility in menu."""
        self.themes_visible = not self.themes_visible
        debug(f'ToggleThemesVisible: {self.themes_visible}')
        self._load_default_config()

    def RandomizeColor(self):
        """Set a random family color."""
        import random
        new_color = [random.random() * 0.7 + 0.15 for _ in range(3)]
        debug(f'RandomizeColor: {new_color}')
        self.color = new_color
        self.ui.update_family_color(self.color)

    def _update_time_label(self):
        """Update check_time label to current time."""
        import datetime
        time_str = datetime.datetime.now().strftime("%H:%M:%S")

        # Direct table update
        table = self.ownerComp.op('replace_index')
        if table:
            table['Check Time', 1] = f"🕐 {time_str}"
            self.ownerComp.op('OP_fam').cook(force=True)

        # # Alternative: using ExportConfig/ImportConfig
        # config = self.ExportConfig()
        # config['tables']['replace_index']['Check Time'] = f"🕐 {time_str}"
        # self.ImportConfig(config)

    def _show_options_dialog(self):
        """Show options dialog with Uninstall/Cancel."""
        fam = self.FamilyName.val
        choice = ui.messageBox(
            f'{fam} Options',
            f'What would you like to do with {fam}?',
            buttons=['Uninstall', 'Cancel']
        )
        if choice == 0:  # Uninstall
            debug('User chose Uninstall')
            self.ownerComp.par.Install = 0
            self.Install()

    # ==================== Hooks ====================

    def PlaceOp(self, panelValue, lookup_name):
        """
        Hook: Called before operator placement.

        ActionOp Pattern:
        - Return True  -> place operator normally
        - Return False -> cancel, close menu
        - Return None  -> cancel, KEEP MENU OPEN (ActionOp behavior)

        Args:
            panelValue: Raw panel value from TAB menu
            lookup_name: Lowercase operator name

        Returns:
            True/False/None as described above
        """
        debug(f'PlaceOp called: panelValue={panelValue}, lookup_name={lookup_name}')

        # Toggle themes visibility
        if lookup_name == 'show_themes':
            debug(f'ActionOp: show_themes toggle')
            self.ToggleThemesVisible()
            return None

        # See options - show message box
        if lookup_name == 'see_options':
            debug(f'ActionOp: see_options')
            return self._show_options_dialog()

        # Random color
        if lookup_name == 'random':
            debug(f'ActionOp: random color')
            self.RandomizeColor()
            return None

        # Open dotsimulate.com
        if lookup_name == 'dotsimulate':
            debug(f'ActionOp: dotsimulate')
            import webbrowser
            webbrowser.open('https://dotsimulate.com')
            return False  # Close menu

        # Check time - update label dynamically
        if lookup_name == 'check_time':
            debug(f'ActionOp: check_time')
            self._update_time_label()
            return None  # Keep menu open

        # Check if this is a theme action operator
        if lookup_name in self.THEMES:
            debug(f'ActionOp detected: {lookup_name} - executing theme change')
            self.SetTheme(lookup_name)
            return None

        # Normal operator - proceed with placement
        debug(f'Normal op: {lookup_name} - proceeding with placement')
        return True

    def PostPlaceOp(self, clone):
        """
        Hook: Called after operator is placed.

        Store current theme on the operator for reference.
        Set par.Color if the operator has it.
        """
        debug(f'PostPlaceOp: {clone.name} at {clone.path}')
        clone.store('example_theme', self.theme)

        # Set par.Color on simple operator
        if clone.name.startswith('simple'):
            clone.par.Colorr = self.color[0]
            clone.par.Colorg = self.color[1]
            clone.par.Colorb = self.color[2]

        debug(f"Placed '{clone.name}' with theme '{self.theme}'")

    def GetExcludedTags(self):
        """
        Hook: Tags to exclude from batch operations (stubs, updates).

        ActionOps shouldn't be included in stub creation since they
        don't represent placeable operators.
        """
        return {self.ACTION_TAG}

    def GetCategoryTags(self):
        """
        Hook: Category tags for operator type detection.

        Used by tag_helpers to identify operator types.
        """
        return {self.ACTION_TAG}

    # ==================== Config ====================

    def _load_default_config(self):
        """
        Load default configuration for operator categories.

        Uses ImportConfig to set up group_mapping and settings tables.
        """
        fam = self.FamilyName.val

        # Build group_mapping based on themes_visible state
        if self.themes_visible:
            group_mapping = {
                "Settings": ["show_themes", "dark", "light", "ice", "volcano", "random", "see_options", "check_time", "dotsimulate"]
            }
            toggle_label = "[ Hide Themes ]"
        else:
            group_mapping = {
                "Settings": ["show_themes", "see_options", "check_time", "dotsimulate"]
            }
            toggle_label = "[ Show Themes ]"

        # Exclude theme operators when hidden
        if self.themes_visible:
            os_incompatible = {}
        else:
            os_incompatible = {
                "dark": {"windows": 1, "mac": 1, "exclude": 1},
                "light": {"windows": 1, "mac": 1, "exclude": 1},
                "ice": {"windows": 1, "mac": 1, "exclude": 1},
                "volcano": {"windows": 1, "mac": 1, "exclude": 1},
                "random": {"windows": 1, "mac": 1, "exclude": 1},
            }

        config = {
            "tables": {
                "group_mapping": group_mapping,
                "replace_index": {
                    "Show Themes": toggle_label,
                    "See Options": "[ Options... ]",
                    "Dotsimulate": ">> dotsimulate",
                    "Check Time": "🕐 click for time",
                    "Simple": "Simple Color",
                    "Dark": f"{fam} Look 🌙",
                    "Light": f"{fam} Look 🌞",
                    "Ice": f"{fam} Look ❄️",
                    "Volcano": f"{fam} Look 🌋",
                    "Random": f"{fam} Look 🎲"
                },
                "os_incompatible": os_incompatible
            },
            "settings": {
                "sort_within_group": "custom",
                "show_ungrouped": "1",
                "ungrouped_label": "Other",
                "exclude_behavior": "hide"
            }
        }

        success, message = self.ImportConfig(config)
        debug(f'_load_default_config: {message}')
