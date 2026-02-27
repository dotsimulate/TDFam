"""
Configuration system for opfam-create.

Handles JSON import/export and two-way sync between Config DependDict and DAT tables.

Architecture:
    JSON Import -> Config DependDict -> DAT Tables
    DAT Tables (via DATExecute) -> Config DependDict -> JSON Export

Config DependDict is source of truth for code.
DAT Tables are visual/no-code interface.
"""

import json


class ConfigManager:
    """
    Manages configuration tables and settings for an operator family.

    Supports:
    - Two-way sync between Config DependDict and DAT tables
    - JSON import/export
    - Settings table management
    - Group mapping, replace index, OS compatibility, relabel tables
    """

    def __init__(self, installer):
        """
        Initialize the config manager.

        Args:
            installer: The OpFamCreateExt instance
        """
        self.installer = installer
        self.ownerComp = installer.ownerComp
        self._syncing = False  # Loop prevention flag

    # ==================== Sync Methods ====================

    def sync_tables_to_config(self):
        """Read all DAT tables into Config DependDict."""
        config = self.installer.Config
        config['group_mapping'] = self._read_group_mapping_table()
        config['label_replacements'] = self._read_label_replacements_table()
        config['os_incompatible'] = self._read_os_incompatible_table()
        config['relabel_index'] = self._read_relabel_index_table()
        config['settings'] = self._read_settings_table()

    def sync_config_to_tables(self):
        """Write Config DependDict to DAT tables."""
        self._syncing = True
        try:
            config = self.installer.Config
            self._write_group_mapping_table(config['group_mapping'])
            self._write_label_replacements_table(config['label_replacements'])
            self._write_os_incompatible_table(config['os_incompatible'])
            self._write_relabel_index_table(config['relabel_index'])
            self._write_settings_table(config['settings'])
        finally:
            self._syncing = False

    def on_table_change(self, table_name):
        """Called by DATExecute when a config table changes."""
        if self._syncing:
            return  # Prevent loop

        # Sync just the changed table to Config
        config = self.installer.Config
        if table_name == 'group_mapping':
            config['group_mapping'] = self._read_group_mapping_table()
        elif table_name == 'label_replacements':
            config['label_replacements'] = self._read_label_replacements_table()
        elif table_name == 'os_incompatible':
            config['os_incompatible'] = self._read_os_incompatible_table()
        elif table_name == 'relabel_index':
            config['relabel_index'] = self._read_relabel_index_table()
        elif table_name == 'settings':
            config['settings'] = self._read_settings_table()

    # ==================== Read Table Methods ====================

    def _read_group_mapping_table(self):
        """Read group_mapping DAT into dict."""
        table = self.ownerComp.op('group_mapping')
        if not table or table.numRows == 0:
            return {}

        result = {}
        for col in range(table.numCols):
            group_name = table[0, col].val
            if not group_name:
                continue
            operators = []
            for row in range(1, table.numRows):
                op_name = table[row, col].val
                if op_name:
                    operators.append(op_name)
            if operators:
                result[group_name] = operators
        return result

    def _read_label_replacements_table(self):
        """Read label_replacements DAT into dict."""
        table = self.ownerComp.op('label_replacements')
        if not table or table.numRows == 0:
            return {}

        result = {}
        # Check if first row is header
        start_row = 0
        if table.numRows > 0 and table[0, 0].val in ('find', 'old', 'search'):
            start_row = 1

        for row in range(start_row, table.numRows):
            old_str = table[row, 0].val
            new_str = table[row, 1].val if table.numCols > 1 else ''
            if old_str:
                result[old_str] = new_str
        return result

    def _read_os_incompatible_table(self):
        """Read os_incompatible DAT into dict."""
        table = self.ownerComp.op('os_incompatible')
        if not table or table.numRows <= 1:
            return {}

        result = {}
        for row in range(1, table.numRows):
            op_name = table[row, 0].val
            if not op_name:
                continue
            windows = int(table[row, 1].val) if table.numCols > 1 else 1
            mac = int(table[row, 2].val) if table.numCols > 2 else 1
            exclude = int(table[row, 3].val) if table.numCols > 3 else 0
            result[op_name] = {'windows': windows, 'mac': mac, 'exclude': exclude}
        return result

    def _read_relabel_index_table(self):
        """Read relabel_index DAT into dict."""
        table = self.ownerComp.op('relabel_index')
        if not table or table.numRows == 0:
            return {}

        result = {}
        # Check if first row is header
        start_row = 0
        if table.numRows > 0 and table[0, 0].val in ('index', 'idx'):
            start_row = 1

        for row in range(start_row, table.numRows):
            idx_str = table[row, 0].val
            label = table[row, 1].val if table.numCols > 1 else ''
            if idx_str:
                result[str(idx_str)] = label
        return result

    def _read_settings_table(self):
        """Read settings DAT into dict."""
        table = self.ownerComp.op('settings')
        if not table or table.numRows <= 1:
            return {}

        result = {}
        for row in range(1, table.numRows):
            key = table[row, 0].val
            value = table[row, 1].val if table.numCols > 1 else ''
            if key:
                result[key] = value
        return result

    # ==================== Write Table Methods ====================

    def _write_group_mapping_table(self, data):
        """Write dict to group_mapping DAT."""
        table = self.ownerComp.op('group_mapping')
        if not table:
            table = self.ownerComp.create(tableDAT, 'group_mapping')
        table.clear()

        if not data:
            # Empty table still gets placeholder header
            table.appendRow(['group'])
            return

        group_names = list(data.keys())
        max_ops = max(len(ops) for ops in data.values()) if data else 0

        # Header row (group names)
        table.appendRow(group_names)

        # Operator rows
        for row_idx in range(max_ops):
            row = []
            for group_name in group_names:
                ops = data[group_name]
                row.append(ops[row_idx] if row_idx < len(ops) else '')
            table.appendRow(row)

    def _write_label_replacements_table(self, data):
        """Write dict to label_replacements DAT."""
        table = self.ownerComp.op('label_replacements')
        if not table:
            table = self.ownerComp.create(tableDAT, 'label_replacements')
        table.clear()

        # Always add header row
        table.appendRow(['find', 'replace'])

        if not data:
            return

        for old_str, new_str in data.items():
            table.appendRow([old_str, new_str])

    def _write_os_incompatible_table(self, data):
        """Write dict to os_incompatible DAT."""
        table = self.ownerComp.op('os_incompatible')
        if not table:
            table = self.ownerComp.create(tableDAT, 'os_incompatible')
        table.clear()

        # Header row
        table.appendRow(['operator_name', 'windows', 'mac', 'exclude'])

        if not data:
            return

        for op_name, os_vals in data.items():
            windows = os_vals.get('windows', 1)
            mac = os_vals.get('mac', 1)
            exclude = os_vals.get('exclude', 0)
            table.appendRow([op_name, windows, mac, exclude])

    def _write_relabel_index_table(self, data):
        """Write dict to relabel_index DAT."""
        table = self.ownerComp.op('relabel_index')
        if not table:
            table = self.ownerComp.create(tableDAT, 'relabel_index')
        table.clear()

        # Always add header row
        table.appendRow(['index', 'label'])

        if not data:
            return

        for idx_str, label in data.items():
            table.appendRow([idx_str, label])

    def _write_settings_table(self, data):
        """Write dict to settings DAT."""
        table = self.ownerComp.op('settings')
        if not table:
            table = self.ownerComp.create(tableDAT, 'settings')
        table.clear()

        # Header row
        table.appendRow(['key', 'value'])

        if not data:
            return

        for key, value in data.items():
            table.appendRow([key, value])

    # ==================== Settings Convenience Methods ====================

    def ensure_settings_table(self):
        """
        Ensure the settings table exists, create if not.

        Returns:
            tableDAT: The settings table
        """
        settings = self.ownerComp.op('settings')
        if not settings:
            settings = self.ownerComp.create(tableDAT, 'settings')
            settings.appendRow(['key', 'value'])
        return settings

    def get_setting(self, key, default=None):
        """
        Get a setting value from Config DependDict.

        Args:
            key: The setting key
            default: Default value if key not found

        Returns:
            The setting value or default
        """
        settings = self.installer.Config.get('settings', {})
        return settings.get(key, default)

    def set_setting(self, key, value):
        """
        Set a setting value in Config DependDict and sync to table.

        Args:
            key: The setting key
            value: The value to set
        """
        config = self.installer.Config
        if 'settings' not in config or not config['settings']:
            config['settings'] = {}
        config['settings'][key] = value

        # Sync just this setting to table
        self._syncing = True
        try:
            table = self.ensure_settings_table()
            if table.row(key) is None:
                table.appendRow([key, value])
            else:
                table[key, 1] = value
        finally:
            self._syncing = False

    # ==================== Table Management ====================

    def ensure_tables_exist(self):
        """
        Create all config tables with proper headers if they don't exist.
        Call this on init to ensure tables are available for no-code editing.
        """
        # group_mapping - header row contains group names (columns)
        table = self.ownerComp.op('group_mapping')
        if not table:
            table = self.ownerComp.create(tableDAT, 'group_mapping')
            table.clear()
            table.appendRow(['group'])  # Placeholder header

        # label_replacements
        table = self.ownerComp.op('label_replacements')
        if not table:
            table = self.ownerComp.create(tableDAT, 'label_replacements')
            table.clear()
            table.appendRow(['find', 'replace'])

        # os_incompatible
        table = self.ownerComp.op('os_incompatible')
        if not table:
            table = self.ownerComp.create(tableDAT, 'os_incompatible')
            table.clear()
            table.appendRow(['operator_name', 'windows', 'mac', 'exclude'])

        # relabel_index
        table = self.ownerComp.op('relabel_index')
        if not table:
            table = self.ownerComp.create(tableDAT, 'relabel_index')
            table.clear()
            table.appendRow(['index', 'label'])

        # settings
        table = self.ownerComp.op('settings')
        if not table:
            table = self.ownerComp.create(tableDAT, 'settings')
            table.clear()
            table.appendRow(['key', 'value'])

    def ensure_table_headers(self):
        """Ensure existing config tables have proper headers (migration helper)."""
        # label_replacements
        table = self.ownerComp.op('label_replacements')
        if table and table.numRows > 0 and table[0, 0].val not in ('find', 'old', 'search'):
            table.insertRow(['find', 'replace'], 0)

        # relabel_index
        table = self.ownerComp.op('relabel_index')
        if table and table.numRows > 0 and table[0, 0].val not in ('index', 'idx'):
            table.insertRow(['index', 'label'], 0)

    # ==================== Public API ====================

    def import_config(self, source):
        """
        Import JSON config into Config DependDict, then sync to tables.

        Args:
            source: Can be one of:
                - str: File path OR JSON string
                - dict: Config dict directly

        Returns:
            tuple: (success: bool, message: str)
        """
        config_data = None
        source_desc = "config"

        # Parse source
        if isinstance(source, dict):
            config_data = source
            source_desc = "dict"
        elif isinstance(source, str):
            stripped = source.strip()
            if stripped.startswith('{'):
                try:
                    config_data = json.loads(source)
                    source_desc = "JSON string"
                except json.JSONDecodeError as e:
                    return (False, f"JSON parse error: {e}")
            else:
                try:
                    with open(source, 'r') as f:
                        config_data = json.load(f)
                    source_desc = source
                except json.JSONDecodeError as e:
                    return (False, f"JSON parse error: {e}")
                except FileNotFoundError:
                    return (False, f"File not found: {source}")
                except Exception as e:
                    return (False, f"Error reading file: {e}")
        else:
            return (False, f"Invalid source type: {type(source)}")

        # Update Config DependDict (source of truth)
        installer_config = self.installer.Config
        if 'tables' in config_data:
            installer_config['group_mapping'] = config_data['tables'].get('group_mapping', {})
            installer_config['label_replacements'] = config_data['tables'].get('label_replacements') or config_data['tables'].get('replace_index', {})
            installer_config['os_incompatible'] = config_data['tables'].get('os_incompatible', {})
            installer_config['relabel_index'] = config_data['tables'].get('relabel_index', {})
        if 'settings' in config_data:
            installer_config['settings'] = config_data['settings']

        # Sync to tables (visual representation)
        self.sync_config_to_tables()

        # Force recook OP_fam
        op_fam = self.ownerComp.op('OP_fam')
        if op_fam:
            op_fam.cook(force=True)

        return (True, f"Imported config from {source_desc}")

    def _to_plain_dict(self, obj):
        """Recursively convert DependDict and other dict-like objects to plain dicts."""
        if hasattr(obj, 'getRaw'):
            # DependDict - get raw dict
            obj = obj.getRaw()
        if isinstance(obj, dict):
            return {k: self._to_plain_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._to_plain_dict(item) for item in obj]
        else:
            return obj

    def export_config(self, path=None):
        """
        Export config from DependDict to JSON.

        Args:
            path: Full path for JSON output file.
                  If None, returns the config dict directly.

        Returns:
            If path provided: tuple (success: bool, message: str)
            If path is None: dict (the config)
        """
        config = self.installer.Config
        export_data = {
            "tables": {
                "group_mapping": self._to_plain_dict(config['group_mapping']),
                "label_replacements": self._to_plain_dict(config['label_replacements']),
                "os_incompatible": self._to_plain_dict(config['os_incompatible']),
                "relabel_index": self._to_plain_dict(config['relabel_index'])
            },
            "settings": self._to_plain_dict(config['settings'])
        }

        if path is None:
            return export_data

        try:
            with open(path, 'w') as f:
                json.dump(export_data, f, indent=2)
            return (True, f"Exported config to {path}")
        except Exception as e:
            return (False, f"Export error: {e}")
