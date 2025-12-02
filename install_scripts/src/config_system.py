"""
Configuration system for opfam-create.

Handles JSON import/export and settings table management for operator families.
"""

import json


class ConfigManager:
    """
    Manages configuration tables and settings for an operator family.

    Supports:
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

    # ==================== Settings Table ====================

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
        Get a setting value from the settings table.

        Args:
            key: The setting key
            default: Default value if key not found

        Returns:
            The setting value or default
        """
        settings = self.ownerComp.op('settings')
        if settings and settings.row(key):
            return settings[key, 1].val
        return default

    def set_setting(self, key, value):
        """
        Set a setting value in the settings table.

        Args:
            key: The setting key
            value: The value to set
        """
        settings = self.ensure_settings_table()
        if settings.row(key) is None:
            settings.appendRow([key, value])
        else:
            settings[key, 1] = value

    # ==================== Import Helpers ====================

    def _import_group_mapping(self, data):
        """
        Import group_mapping from dict.

        Args:
            data: Group mapping dict {group_name: [operator_names]}
        """
        table = self.ownerComp.op('group_mapping')
        if not table:
            table = self.ownerComp.create(tableDAT, 'group_mapping')

        table.clear()

        if not data:
            return

        group_names = list(data.keys())
        max_ops = max(len(ops) for ops in data.values()) if data else 0

        # Header row
        table.appendRow(group_names)

        # Operator rows
        for row_idx in range(max_ops):
            row = []
            for group_name in group_names:
                ops = data[group_name]
                row.append(ops[row_idx] if row_idx < len(ops) else '')
            table.appendRow(row)

    def _import_replace_index(self, data):
        """
        Import replace_index from dict.

        Args:
            data: Replace mapping {old_string: new_string}
        """
        table = self.ownerComp.op('replace_index')
        if not table:
            table = self.ownerComp.create(tableDAT, 'replace_index')

        table.clear()

        if not data:
            return

        for old_str, new_str in data.items():
            table.appendRow([old_str, new_str])

    def _import_os_incompatible(self, data):
        """
        Import os_incompatible from dict.

        Args:
            data: OS compatibility {op_name: {windows: 0/1, mac: 0/1, exclude: 0/1}}
        """
        table = self.ownerComp.op('os_incompatible')
        if not table:
            table = self.ownerComp.create(tableDAT, 'os_incompatible')

        table.clear()
        table.appendRow(['operator_name', 'windows', 'mac', 'exclude'])

        if not data:
            return

        for op_name, os_vals in data.items():
            windows = os_vals.get('windows', 1)
            mac = os_vals.get('mac', 1)
            exclude = os_vals.get('exclude', 0)
            table.appendRow([op_name, windows, mac, exclude])

    def _import_relabel_index(self, data):
        """
        Import relabel_index from dict.

        Args:
            data: Relabel mapping {index_str: label}
        """
        table = self.ownerComp.op('relabel_index')
        if not table:
            table = self.ownerComp.create(tableDAT, 'relabel_index')

        table.clear()

        if not data:
            return

        for idx_str, label in data.items():
            table.appendRow([idx_str, label])

    def _import_settings(self, data):
        """
        Import settings from dict.

        Args:
            data: Settings {key: value}
        """
        if not data:
            return

        for key, value in data.items():
            self.set_setting(key, value)

    # ==================== Export Helpers ====================

    def _export_group_mapping(self):
        """
        Export group_mapping table to dict.

        Returns:
            dict: {group_name: [operator_names]}
        """
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

            result[group_name] = operators

        return result

    def _export_replace_index(self):
        """
        Export replace_index table to dict.

        Returns:
            dict: {old_string: new_string}
        """
        table = self.ownerComp.op('replace_index')
        if not table or table.numRows == 0:
            return {}

        result = {}
        for row in range(table.numRows):
            old_str = table[row, 0].val
            new_str = table[row, 1].val if table.numCols > 1 else ''
            if old_str:
                result[old_str] = new_str

        return result

    def _export_os_incompatible(self):
        """
        Export os_incompatible table to dict.

        Returns:
            dict: {op_name: {windows: 0/1, mac: 0/1, exclude: 0/1}}
        """
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

    def _export_relabel_index(self):
        """
        Export relabel_index table to dict.

        Returns:
            dict: {index_str: label}
        """
        table = self.ownerComp.op('relabel_index')
        if not table or table.numRows == 0:
            return {}

        result = {}
        for row in range(table.numRows):
            idx_str = table[row, 0].val
            label = table[row, 1].val if table.numCols > 1 else ''
            if idx_str:
                result[str(idx_str)] = label

        return result

    def _export_settings(self):
        """
        Export settings table to dict.

        Returns:
            dict: {key: value}
        """
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

    # ==================== Public API ====================

    def import_config(self, source):
        """
        Import JSON config into tables.

        Args:
            source: Can be one of:
                - str: File path OR JSON string
                - dict: Config dict directly

        Returns:
            tuple: (success: bool, message: str)
        """
        config = None
        source_desc = "config"

        if isinstance(source, dict):
            config = source
            source_desc = "dict"
        elif isinstance(source, str):
            stripped = source.strip()
            if stripped.startswith('{'):
                try:
                    config = json.loads(source)
                    source_desc = "JSON string"
                except json.JSONDecodeError as e:
                    return (False, f"JSON parse error: {e}")
            else:
                try:
                    with open(source, 'r') as f:
                        config = json.load(f)
                    source_desc = source
                except json.JSONDecodeError as e:
                    return (False, f"JSON parse error: {e}")
                except FileNotFoundError:
                    return (False, f"File not found: {source}")
                except Exception as e:
                    return (False, f"Error reading file: {e}")
        else:
            return (False, f"Invalid source type: {type(source)}")

        # Import tables
        if 'tables' in config:
            self._import_group_mapping(config['tables'].get('group_mapping', {}))
            self._import_replace_index(config['tables'].get('replace_index', {}))
            self._import_os_incompatible(config['tables'].get('os_incompatible', {}))
            self._import_relabel_index(config['tables'].get('relabel_index', {}))

        # Import settings
        if 'settings' in config:
            self._import_settings(config['settings'])

        # Force recook OP_fam
        op_fam = self.ownerComp.op('OP_fam')
        if op_fam:
            op_fam.cook(force=True)

        return (True, f"Imported config from {source_desc}")

    def export_config(self, path=None):
        """
        Export current tables to JSON config.

        Args:
            path: Full path for JSON output file.
                  If None, returns the config dict directly.

        Returns:
            If path provided: tuple (success: bool, message: str)
            If path is None: dict (the config)
        """
        config = {
            "tables": {
                "group_mapping": self._export_group_mapping(),
                "replace_index": self._export_replace_index(),
                "os_incompatible": self._export_os_incompatible(),
                "relabel_index": self._export_relabel_index()
            },
            "settings": self._export_settings()
        }

        if path is None:
            return config

        try:
            with open(path, 'w') as f:
                json.dump(config, f, indent=2)
            return (True, f"Exported config to {path}")
        except Exception as e:
            return (False, f"Export error: {e}")
